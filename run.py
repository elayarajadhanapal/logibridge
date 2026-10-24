"""
run.py — start the whole LogiBridge stack with one command.

    python run.py                       # broker + every implemented service + dashboard
    python run.py --anomaly combined    # simulator starts in another mode
    python run.py --no-browser          # do not open the dashboard

What it does:
  1. starts a Mosquitto broker: WebSockets 9001 for the dashboard, TCP 1883 for the
     services (1884 when 1883 is already taken, e.g. by the Windows Mosquitto service)
  2. starts every service in SERVICES whose file exists, with the broker address in
     LOGIBRIDGE_MQTT_HOST / LOGIBRIDGE_MQTT_PORT
  3. opens dashboard/logiedge_dashboard.html, which connects by itself
Ctrl+C stops everything: services first (they publish "offline"), then the broker.

If a broker is already listening on 9001 (an earlier run, or one started by hand with
deployment/mosquitto.conf), it is reused; the TCP port is the one that reaches that same
broker, verified with a probe message.
"""
import argparse
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DASHBOARD = ROOT / "dashboard" / "logiedge_dashboard.html"
WS_PORT = 9001

# Start order: consumers first, the simulator (the data source) last.
# A service is skipped until its file exists, so new modules join automatically.
SERVICES = [
    ("preprocessing", "data_pipeline/preprocessing.py"),
    ("inference", "inference/inference_service.py"),
    ("drift_monitor", "monitoring/drift_monitor.py"),
    ("uplink_agent", "edge_runtime/uplink_agent.py"),
    ("node_monitor", "edge_runtime/node_monitor.py"),
    ("simulator", "data_pipeline/simulator.py"),
]


def port_in_use(port):
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def find_mosquitto():
    for path in (shutil.which("mosquitto"), r"C:\Program Files\mosquitto\mosquitto.exe",
                 "/usr/sbin/mosquitto", "/opt/homebrew/sbin/mosquitto", "/usr/local/sbin/mosquitto"):
        if path and os.path.exists(path):
            return path
    return None


def tcp_port_of_ws_broker(candidates=(1883, 1884)):
    """TCP port that reaches the same broker as WebSockets 9001, or None.

    A message published over TCP must arrive at a subscriber on 9001. This tells the
    project broker apart from another broker that merely holds 1883 (e.g. the Windows
    Mosquitto service).
    """
    import paho.mqtt.client as mqtt
    topic = f"logibridge/_probe/{os.getpid()}"
    got = []
    ws = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, transport="websockets")
    ws.on_message = lambda c, u, m: got.append(m.payload.decode())
    ws.connect("localhost", WS_PORT)
    ws.subscribe(topic)
    ws.loop_start()
    time.sleep(0.3)
    try:
        for port in candidates:
            if not port_in_use(port):
                continue
            pub = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
            pub.connect("localhost", port)
            pub.loop_start()
            pub.publish(topic, str(port)).wait_for_publish(1)
            time.sleep(0.3)
            pub.loop_stop()
            pub.disconnect()
            if str(port) in got:
                return port
        return None
    finally:
        ws.loop_stop()
        ws.disconnect()


def start_broker():
    """Return (broker process or None if reused, TCP port for the services)."""
    if port_in_use(WS_PORT):
        tcp = tcp_port_of_ws_broker()
        if tcp is None:
            sys.exit(f"[run] port {WS_PORT} is in use, but not by a broker reachable on TCP 1883/1884. "
                     f"Stop the program using it and run again.")
        print(f"[run] reusing the broker already running on {WS_PORT} (services use TCP {tcp})")
        return None, tcp
    exe = find_mosquitto()
    if not exe:
        sys.exit("[run] Mosquitto not found. Install it: winget install EclipseFoundation.Mosquitto")
    tcp = 1883 if not port_in_use(1883) else 1884
    if tcp == 1884:
        print("[run] port 1883 is taken (probably the Windows Mosquitto service): services use 1884")
    conf = Path(tempfile.mkdtemp(prefix="logibridge-")) / "mosquitto.conf"
    conf.write_text(f"listener {tcp}\nlistener {WS_PORT}\nprotocol websockets\nallow_anonymous true\n")
    broker = subprocess.Popen([exe, "-c", str(conf)], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    for _ in range(50):
        if port_in_use(WS_PORT) and port_in_use(tcp):
            print(f"[run] broker up: TCP {tcp} (services), WebSockets {WS_PORT} (dashboard)")
            return broker, tcp
        if broker.poll() is not None:
            break
        time.sleep(0.1)
    sys.exit("[run] the broker did not start")


def main():
    p = argparse.ArgumentParser(description="Start the LogiBridge stack and the dashboard")
    p.add_argument("--anomaly", default="none", choices=("none", "temp_drift", "vibration", "combined"),
                   help="initial simulator mode (also switchable from the dashboard)")
    p.add_argument("--no-browser", action="store_true", help="do not open the dashboard")
    args = p.parse_args()

    broker, tcp = start_broker()
    env = dict(os.environ, LOGIBRIDGE_MQTT_HOST="localhost", LOGIBRIDGE_MQTT_PORT=str(tcp),
               LOGIBRIDGE_IFACE="mqtt", PYTHONUNBUFFERED="1")
    procs = []
    for name, rel in SERVICES:
        if not (ROOT / rel).exists():
            print(f"[run] {name:<14} not implemented yet: skipped ({rel})")
            continue
        extra = ["--anomaly", args.anomaly] if name == "simulator" else []
        procs.append((name, subprocess.Popen([sys.executable, str(ROOT / rel), *extra], cwd=ROOT, env=env)))
        print(f"[run] {name:<14} started")
        time.sleep(0.5)                      # consumers subscribe before the data starts

    if not args.no_browser:
        webbrowser.open(DASHBOARD.as_uri())
        print(f"[run] dashboard opened: {DASHBOARD}")
    print("[run] running - press Ctrl+C to stop everything")

    exited = set()
    try:
        while True:
            for name, proc in procs:
                if proc.poll() is not None and name not in exited:
                    exited.add(name)
                    print(f"[run] {name} exited with code {proc.returncode}")
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[run] stopping...")
    finally:
        # Ctrl+C reaches the services too (same console); give them time to publish "offline".
        deadline = time.time() + 5
        for _, proc in procs:
            try:
                proc.wait(timeout=max(0.1, deadline - time.time()))
            except subprocess.TimeoutExpired:
                proc.terminate()
        if broker:
            broker.terminate()
        print("[run] stopped")


if __name__ == "__main__":
    main()
