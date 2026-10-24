# LogiEdge dashboard interfaces

How every service feeds `dashboard/logiedge_dashboard.html`, and what each service must do when the dashboard sends it a command. One page per team member: find your service in section 4, publish what it lists, and run the contract test.

> **Engineers: you do not implement this by hand.** The rules below are already coded in `dashboard/dashboard_api.py` and exposed as plain methods in each folder's `<module>_dashboard_iface.py`. Start with [DASHBOARD_IFACE.md](DASHBOARD_IFACE.md). This page is the reference behind it (and material for Report Section 2).

## 1. How the dashboard uses MQTT

The dashboard connects to Mosquitto over WebSockets (`ws://localhost:9001`). Python services connect over TCP (`localhost:1883`). Both reach the same broker, so a service never talks to the dashboard directly.

Every stage on the dashboard has a built-in mock. When your service publishes on its topic, the dashboard uses your data instead. If your messages stop for 5 seconds, the mock takes over again. While any sensor, feature or inference stream is coming from Python, the dashboard locks its clock to 1× real time so timestamps line up.

The dashboard owns the scenario: route timing, signal gaps, anomaly injection, model choice. It sends these as commands on the `control` topic. Services report what they actually did on their own topics. The dashboard never assumes a command worked; it waits for the report (for example `model/active` after a model switch).

## 2. Common rules for every message

Topic prefix: `logibridge/trucks/{truck_id}/`. Default truck id: `MH15-RF-0427` (change it in the dashboard's Connect tab if you use another).

Payload: UTF-8 JSON object. Every message carries this envelope plus its own fields:

| Field | Type | Meaning |
|---|---|---|
| `v` | int | Schema version, currently `1` |
| `truck_id` | string | Same as in the topic |
| `ts` | float | Unix seconds, **data time** (when the reading or event happened, not when it was sent) |
| `seq` | int | Increments by 1 per message from your service; lets receivers spot loss and duplicates |
| `src` | string | Your service name, e.g. `"simulator"` |

The dashboard ignores fields it does not know, so you can add fields freely. It rejects a message only if a required field is missing or has the wrong type; rejected messages appear in Details → Event log and show ✗ in the Connect tab.

Client settings for every Python service:

| Setting | Value | Why |
|---|---|---|
| Client ID | `logiedge-<service>-<truck_id>` | Fixed, so persistent sessions and logs identify you |
| Keepalive | 10 s | Broker notices a dead service within ~15 s |
| Last will | topic `status/<service>`, payload `{"online": false}`, QoS 1, retain | Dashboard marks your stage offline if you crash |
| On connect | publish `status/<service>` `{"online": true}`, QoS 1, retain | Do it inside `on_connect` so it repeats after a reconnect |
| On clean exit | publish `{"online": false}` retained, then disconnect | A clean disconnect does not fire the will |

The paho-mqtt calls that implement this are `Client(client_id=...)`, `will_set(topic, payload, qos=1, retain=True)` **before** `connect(host, 1883, keepalive=10)`, then `loop_start()`. See the paho-mqtt documentation for details.

## 3. Topic contract

All topics below are relative to `logibridge/trucks/{truck_id}/` unless they start with `logibridge/`.

| Topic | Publisher | Required fields (plus envelope) | QoS | Retain | Rate | Dashboard effect |
|---|---|---|---|---|---|---|
| `sensors/temperature` | simulator | `value` (°C, float) | 0 | no | 1 Hz | Sensor card, temperature trend, cargo reading |
| `sensors/vibration` | simulator | `value` (g RMS, float) | 0 | no | 0.5 Hz | Sensor card, vibration trend |
| `sensors/door` | simulator | `state`: `"OPEN"` or `"CLOSE"` | 1 | no | on event | Door state and timeline |
| `features` | preprocessing | `window_start` (float), `raw` (6 floats), `norm` (6 floats) | 0 | no | every 10 s | Feature table in Details; feeds the mock model if no inference service |
| `inference` | inference_service | `class` (0/1/2), `probs` (3 floats, sum 1), `latency_ms`, `model` | 1 | no | every 10 s | Class badge, probability bars, latency |
| `model/active` | inference_service | `model` (`M1`/`M2`/`M3`), `size_kb`, `sha256` | 1 | yes | on load | Confirms the model switch, OTA banner |
| `drift` | drift_monitor | `psi` (float); optional `bins` (4 floats), `n` | 1 | no | every 60 s | PSI chart and drift alerts |
| `alerts` | uplink_agent | `class` (0 clear / 1 / 2), `msg` (string), `raised_ts` (float) | 1 | no | on event | Operations-centre list; lateness = `ts − raised_ts` |
| `storage` | uplink_agent | `stored_bytes`, `queued_bytes`, `sent_bytes` (ints); optional `queued_records` | 1 | yes | 1 Hz | Local storage card, bytes sent, ops received |
| `uplink/sync` | uplink_agent | `records`, `bytes` (ints); optional `gap_s` | 1 | no | on reconnect | "Signal back · syncing …" banner |
| `link` | uplink_agent | `cellular` (bool) | 1 | yes | on change | Display only; the route decides signal |
| `node/metrics` | node_monitor | `cpu_pct`, `power_w` (floats); optional `ram_used_kb`, `ram_total_kb`, `power_src` (`"estimate"`/`"measured"`) | 0 | no | 1 Hz | Edge-node compute, memory and power meters |
| `status/<service>` | every service | `online` (bool) | 1 | yes | on connect, LWT | Live-service badges on the main screen |
| `logibridge/sim/models` | benchmark | `{"M1": {...}, "M2": {...}, "M3": {...}}` with any of `sizeKB`, `latencyMs`, `p95Ms`, `accuracy`, `recallC2`, `energyMJ` | 1 | yes | once | Model column numbers replace placeholders |
| `control` | **dashboard** | one of `anomaly`, `model`, `cellular` (see section 5) | 1 | no | on user action or route event | — |

Service names used in `status/<service>`: `simulator`, `preprocessing`, `inference`, `drift_monitor`, `uplink_agent`, `node_monitor`.

## 4. What each service must publish to appear on the dashboard

**simulator.py** — the three `sensors/*` topics, `status/simulator`, and must subscribe to `control`. Use the reading's own time as `ts`. If you run faster than real time (for dataset generation), keep `ts` spaced 1 s apart in data time.

**preprocessing.py** — `features` and `status/preprocessing`. Publish both `raw` and `norm`. If `training_stats.npy` is missing, publish `raw` only and log a warning; never compute stats from live data.

**inference_service.py** — `inference`, `model/active` (retained, after every successful load), `status/inference`. Subscribes to `control` for model changes.

**drift_monitor.py** — `drift` once per minute and `status/drift_monitor`. Also print `[LOGIBRIDGE DRIFT ALERT] PSI=x.xxx` locally; the console output is what the brief asks to see.

**uplink_agent.py** — `storage` every second, `uplink/sync` when it flushes, `alerts` for every alert it delivers to operations, `link` on change, `status/uplink_agent`. Subscribes to `inference` (to write window records and raise alerts) and `control` (for `cellular`). Once this service is online, the dashboard stops raising its own edge alerts and shows yours, so the operations panel is exactly what your agent delivered.

**node_monitor.py** — `node/metrics` every second, `status/node_monitor`. Read CPU and RAM with `psutil`. Laptop power cannot be measured, so send an estimate with `power_src: "estimate"` and say so in the report.

**benchmark.py** — publish `logibridge/sim/models` once, retained, after benchmarking. Alternative: paste `benchmark_results.csv` into the dashboard's Connect tab.

## 5. Commands the dashboard sends on `control`

Subscribe at QoS 1. Every command is idempotent: receiving the same one twice must be harmless.

| Payload | Who acts | Required behaviour |
|---|---|---|
| `{"anomaly": "none" \| "temp_drift" \| "vibration" \| "combined"}` | simulator | Switch mode immediately without restarting. Same semantics as `--anomaly`. Switching back to `none` resets any accumulated drift offset, so PSI can recover. |
| `{"model": "M1" \| "M2" \| "M3"}` | inference_service | Load that model file, then publish `model/active`. If loading fails, keep the old model and do not publish `model/active`. |
| `{"cellular": true \| false}` | uplink_agent | Treat the link as up or down. While down, queue instead of sending. On `true`, flush the queue, then publish `uplink/sync`. |

The dashboard sends `cellular` automatically as the truck enters and leaves each signal gap on the route, and when you press the On/Off buttons.

## 6. Testing your service against the contract

1. Start Mosquitto with both listeners (1883 TCP, 9001 WebSockets) using `deployment/mosquitto.conf` (see `docs/SETUP.md`).
2. Open the dashboard → Details → Connect your code → Connect.
3. Run your service. Its rows in the topic table should show ✓ and a recent "last seen". A ✗ means a required field is missing or wrongly typed; Details → Event log shows the rejected payload.
4. To see raw traffic: `mosquitto_sub -t "logibridge/#" -v`.
5. To check the dashboard side without any real service: run the demo in any `<module>_dashboard_iface.py` (e.g. `python inference/inference_dashboard_iface.py`). It publishes valid fake data on that module's topics and prints the control messages the dashboard sends back. See [DASHBOARD_IFACE.md](DASHBOARD_IFACE.md).

## 7. Changing the contract

Topic names can be edited in the dashboard's Connect tab without code changes, so the tree can follow the team's `mqtt_architecture.md`. To add a new stream to the dashboard itself: add it to `TOPICS`, `SCHEMA` and `EXAMPLES` in the HTML, add a branch in `Sim.ext()`, and add a self-test (see `dashboard/README.md`).
