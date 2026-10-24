"""
dashboard_api.py — the one place that knows the LogiBridge MQTT contract.

Module engineers do NOT import this file directly. Each module has a small
`<module>_dashboard_iface.py` with plain methods such as `temperature(4.1)`;
those methods call `DashboardLink.publish()` below.

What this file does for every service, so nobody has to repeat it:
  * connects to Mosquitto (localhost:1883) in the background and keeps reconnecting
  * adds the envelope {v, truck_id, ts, seq, src} to every message
  * checks every payload against the contract (docs/INTERFACES.md) and raises
    ValueError with a clear message if a field is missing, wrong, NaN or inf
  * converts numpy numbers and arrays to plain JSON
  * publishes retained status/<service> {"online": true} on connect, with a
    last will {"online": false} so the dashboard notices a crash
  * delivers dashboard commands on `control` (anomaly / model / cellular)
  * delivers messages from other services (e.g. sensors -> preprocessing)

Mode, chosen with the environment variable LOGIBRIDGE_IFACE:
  mqtt  (default)  talk to the broker
  print            print every message as JSON instead (no broker needed)
  off              validate only, send nothing
"""
import json
import math
import os
import threading
import time

import paho.mqtt.client as mqtt

SCHEMA_VERSION = 1
DEFAULT_TRUCK_ID = "MH15-RF-0427"
DEFAULT_HOST = os.environ.get("LOGIBRIDGE_MQTT_HOST", "localhost")
DEFAULT_PORT = int(os.environ.get("LOGIBRIDGE_MQTT_PORT", "1883"))

ANOMALY_MODES = ("none", "temp_drift", "vibration", "combined")
MODEL_IDS = ("M1", "M2", "M3")
CLASSES = (0, 1, 2)                      # 0 Normal, 1 Warning, 2 Critical


# ---------------------------------------------------------------------------
# Field checks. Each returns None when the value is fine, else a short reason.
# ---------------------------------------------------------------------------
def _number(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return "must be a number"
    if not math.isfinite(v):
        return f"must be finite, got {v}"
    return None


def _integer(v):
    if isinstance(v, bool) or not isinstance(v, int):
        return "must be an integer"
    return None


def _boolean(v):
    return None if isinstance(v, bool) else "must be true or false"


def _text(v):
    return None if isinstance(v, str) else "must be a string"


def _one_of(*allowed):
    def check(v):
        return None if v in allowed else f"must be one of {list(allowed)}, got {v!r}"
    return check


def _numbers(length):
    def check(v):
        if not isinstance(v, list) or len(v) != length:
            return f"must be a list of {length} numbers"
        for i, x in enumerate(v):
            reason = _number(x)
            if reason:
                return f"[{i}] {reason}"
        return None
    return check


def _probabilities(v):
    reason = _numbers(3)(v)
    if reason:
        return reason
    if abs(sum(v) - 1.0) > 0.02:
        return f"must sum to 1, got {sum(v):.3f}"
    return None


def _model_metrics(v):
    if not isinstance(v, dict):
        return "must be an object"
    allowed = ("sizeKB", "latencyMs", "p95Ms", "accuracy", "recallC2", "energyMJ")
    for key, x in v.items():
        if key not in allowed:
            return f"unknown metric {key!r}, use {list(allowed)}"
        if _number(x):
            return f"{key} must be a finite number"
    return None


# ---------------------------------------------------------------------------
# The contract: stream name -> topic, QoS, retain, required and optional fields.
# Topics are relative to logibridge/trucks/{truck_id}/ unless they start with
# "logibridge/". Keep this table identical to docs/INTERFACES.md section 3.
# ---------------------------------------------------------------------------
STREAMS = {
    "temperature": dict(topic="sensors/temperature", qos=0, retain=False,
                        required={"value": _number}),
    "vibration": dict(topic="sensors/vibration", qos=0, retain=False,
                      required={"value": _number}),
    "door": dict(topic="sensors/door", qos=1, retain=False,
                 required={"state": _one_of("OPEN", "CLOSE")}),
    "features": dict(topic="features", qos=0, retain=False,
                     required={"window_start": _number, "raw": _numbers(6)},
                     optional={"norm": _numbers(6)}),
    "inference": dict(topic="inference", qos=1, retain=False,
                      required={"class": _one_of(*CLASSES), "probs": _probabilities,
                                "latency_ms": _number, "model": _one_of(*MODEL_IDS)}),
    "model_active": dict(topic="model/active", qos=1, retain=True,
                         required={"model": _one_of(*MODEL_IDS), "size_kb": _number},
                         optional={"sha256": _text}),
    "drift": dict(topic="drift", qos=1, retain=False,
                  required={"psi": _number},
                  optional={"bins": _numbers(4), "n": _integer}),
    "alerts": dict(topic="alerts", qos=1, retain=False,
                   required={"class": _one_of(*CLASSES), "msg": _text, "raised_ts": _number}),
    "storage": dict(topic="storage", qos=1, retain=True,
                    required={"stored_bytes": _integer, "queued_bytes": _integer,
                              "sent_bytes": _integer},
                    optional={"queued_records": _integer}),
    "sync": dict(topic="uplink/sync", qos=1, retain=False,
                 required={"records": _integer, "bytes": _integer},
                 optional={"gap_s": _number}),
    "link": dict(topic="link", qos=1, retain=True,
                 required={"cellular": _boolean}),
    "node": dict(topic="node/metrics", qos=0, retain=False,
                 required={"cpu_pct": _number, "power_w": _number},
                 optional={"ram_used_kb": _number, "ram_total_kb": _number,
                           "power_src": _one_of("estimate", "measured")}),
    "models": dict(topic="logibridge/sim/models", qos=1, retain=True,
                   required={}, optional={m: _model_metrics for m in MODEL_IDS}),
    "status": dict(topic="status/{service}", qos=1, retain=True,
                   required={"online": _boolean}),
}

# Commands the dashboard sends on `control`, and the values each may carry.
CONTROL_TOPIC = "control"
CONTROL_COMMANDS = {
    "anomaly": _one_of(*ANOMALY_MODES),
    "model": _one_of(*MODEL_IDS),
    "cellular": _boolean,
}

ENVELOPE_FIELDS = ("v", "truck_id", "ts", "seq", "src")


def to_plain(value):
    """numpy scalars/arrays and tuples -> plain Python, so json.dumps works."""
    if hasattr(value, "tolist"):          # numpy array or numpy scalar
        return value.tolist()
    if isinstance(value, (list, tuple)):
        return [to_plain(x) for x in value]
    if isinstance(value, dict):
        return {k: to_plain(x) for k, x in value.items()}
    return value


def check_payload(stream, fields):
    """Raise ValueError if `fields` does not match the contract for `stream`."""
    if stream not in STREAMS:
        raise ValueError(f"unknown stream {stream!r}; known: {sorted(STREAMS)}")
    spec = STREAMS[stream]
    for name, check in spec["required"].items():
        if name not in fields:
            raise ValueError(f"{stream}: missing required field {name!r}")
        reason = check(fields[name])
        if reason:
            raise ValueError(f"{stream}.{name} {reason}")
    for name, check in spec.get("optional", {}).items():
        if fields.get(name) is not None:
            reason = check(fields[name])
            if reason:
                raise ValueError(f"{stream}.{name} {reason}")


class DashboardLink:
    """One MQTT connection for one service (simulator, preprocessing, ...)."""

    def __init__(self, service, truck_id=DEFAULT_TRUCK_ID, host=DEFAULT_HOST,
                 port=DEFAULT_PORT, announce=True, connect_timeout=3.0):
        self.service = service
        self.truck_id = truck_id
        self.base = f"logibridge/trucks/{truck_id}/"
        self.mode = os.environ.get("LOGIBRIDGE_IFACE", "mqtt").lower()
        self.announce = announce          # publish status/<service>? (False for one-shot tools)
        self._seq = 0
        self._lock = threading.Lock()
        self._handlers = {}               # full topic -> list of callback(payload dict)
        self._control = {}                # command name -> list of callback(value)
        self._last_info = None
        self._client = None

        if self.mode not in ("mqtt", "print", "off"):
            raise ValueError("LOGIBRIDGE_IFACE must be mqtt, print or off")
        if self.mode != "mqtt":
            return

        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                                   client_id=f"logiedge-{service}-{truck_id}")
        self._client.max_queued_messages_set(1000)   # bounded buffer while the broker is away
        if announce:
            self._client.will_set(self.topic("status"), self._encode("status", {"online": False}),
                                  qos=1, retain=True)
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        self._connected = threading.Event()
        self._client.connect_async(host, port, keepalive=10)
        self._client.loop_start()
        if not self._connected.wait(connect_timeout):
            print(f"[{service}] WARNING: no MQTT broker at {host}:{port} yet — "
                  f"retrying in the background; messages are dropped until it connects")

    # ---- topics and messages ------------------------------------------------
    def topic(self, stream):
        t = STREAMS[stream]["topic"].replace("{service}", self.service)
        return t if t.startswith("logibridge/") else self.base + t

    def _encode(self, stream, fields, ts=None):
        with self._lock:
            self._seq += 1
            seq = self._seq
        msg = {"v": SCHEMA_VERSION, "truck_id": self.truck_id,
               "ts": float(time.time() if ts is None else ts), "seq": seq, "src": self.service}
        msg.update(fields)
        return json.dumps(msg)

    def publish(self, stream, fields, ts=None):
        """Validate and send one message. `ts` = data time in Unix seconds (default: now)."""
        fields = {k: to_plain(v) for k, v in fields.items() if v is not None}
        check_payload(stream, fields)
        ts = to_plain(ts)
        if ts is not None and _number(ts):
            raise ValueError(f"{stream}.ts {_number(ts)}")
        payload = self._encode(stream, fields, ts)
        spec, topic = STREAMS[stream], self.topic(stream)
        if self.mode == "print":
            print(f"{topic} {payload}")
        elif self.mode == "mqtt":
            self._last_info = self._client.publish(topic, payload, qos=spec["qos"],
                                                   retain=spec["retain"])

    # ---- receiving ------------------------------------------------------------
    def subscribe(self, stream, callback):
        """Call `callback(payload_dict)` for every message another service publishes on `stream`."""
        topic = self.topic(stream)
        self._handlers.setdefault(topic, []).append(callback)
        if self.mode == "mqtt" and self._connected.is_set():
            self._client.subscribe(topic, qos=STREAMS[stream]["qos"])

    def on_control(self, command, callback):
        """Call `callback(value)` when the dashboard sends {command: value} on `control`."""
        if command not in CONTROL_COMMANDS:
            raise ValueError(f"unknown control command {command!r}; known: {sorted(CONTROL_COMMANDS)}")
        self._control.setdefault(command, []).append(callback)
        topic = self.base + CONTROL_TOPIC
        if self.mode == "mqtt" and self._connected.is_set():
            self._client.subscribe(topic, qos=1)

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            print(f"[{self.service}] MQTT connect refused: {reason_code}")
            return
        # Runs again after every reconnect, so status and subscriptions are restored.
        # Set first: a subscribe() racing with this then subscribes itself (twice is harmless).
        self._connected.set()
        if self.announce:
            client.publish(self.topic("status"), self._encode("status", {"online": True}),
                           qos=1, retain=True)
        for topic in list(self._handlers):
            client.subscribe(topic, qos=1)
        if self._control:
            client.subscribe(self.base + CONTROL_TOPIC, qos=1)

    def _on_message(self, client, userdata, message):
        try:
            payload = json.loads(message.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            print(f"[{self.service}] ignored non-JSON message on {message.topic}")
            return
        if message.topic == self.base + CONTROL_TOPIC:
            for command, callbacks in list(self._control.items()):
                if command in payload:
                    if CONTROL_COMMANDS[command](payload[command]):
                        print(f"[{self.service}] ignored invalid control {command}={payload[command]!r}")
                        continue
                    for cb in callbacks:
                        self._safe_call(cb, payload[command])
        for cb in list(self._handlers.get(message.topic, [])):
            self._safe_call(cb, payload)

    def _safe_call(self, callback, arg):
        # A bug in a callback must not kill the MQTT network thread.
        try:
            callback(arg)
        except Exception as e:  # noqa: BLE001
            print(f"[{self.service}] error in callback {getattr(callback, '__name__', callback)}: {e!r}")

    # ---- shutdown -------------------------------------------------------------
    def close(self):
        """Mark the service offline (retained) and disconnect cleanly."""
        if self.mode != "mqtt":
            return
        if self.announce:
            self._last_info = self._client.publish(self.topic("status"),
                                                   self._encode("status", {"online": False}),
                                                   qos=1, retain=True)
        if self._last_info is not None:
            try:
                self._last_info.wait_for_publish(timeout=2.0)
            except (RuntimeError, ValueError):
                pass                      # not connected: nothing more we can do
        self._client.disconnect()
        self._client.loop_stop()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
