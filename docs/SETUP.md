# Development setup

Everything runs on one Windows laptop: a local Mosquitto broker, the Python services, and the dashboard in a browser. Commands below are for PowerShell from the repository root.

## 1. Python environment

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

The inference container uses `python:3.11-slim` (brief, Task D2). The local venv can be newer; anything that must match the container is tested inside Docker.

## 2. Mosquitto broker

Installed at `C:\Program Files\mosquitto` (`winget install EclipseFoundation.Mosquitto`). It is not on `PATH`, so call it by full path.

The Windows installer also registers a `mosquitto` service that listens on 1883 only. Stop it first, otherwise the port is taken:

```powershell
Stop-Service mosquitto        # admin PowerShell; or: net stop mosquitto
```

Start the project broker (TCP 1883 for Python, WebSockets 9001 for the dashboard) and keep this terminal open:

```powershell
& "C:\Program Files\mosquitto\mosquitto.exe" -c deployment/mosquitto.conf -v
```

Watch all project traffic in another terminal:

```powershell
& "C:\Program Files\mosquitto\mosquitto_sub.exe" -t "logibridge/#" -v
```

## 3. Dashboard

1. Open `dashboard/logiedge_dashboard.html` in a browser (double-click is fine; it loads mqtt.js from jsdelivr, so it needs internet once).
2. Details → Connect your code → URL `ws://localhost:9001`, truck `MH15-RF-0427` → Connect.
3. Without any Python service running, every stage uses the built-in mock.

## 4. Smoke test (broker + dashboard, no project code)

Run the demo of any module interface, e.g. in two terminals:

```powershell
python data_pipeline/data_pipeline_dashboard_iface.py
python inference/inference_dashboard_iface.py
```

Their rows in the dashboard's topic table should show ✓ within a few seconds and the sensor, feature and class stages go live. Switching the anomaly mode to `combined` makes the temperature drift; clicking a model button prints `control: model -> M3` in the inference terminal. This proves the broker, both listeners, and the dashboard wiring before any LogiBridge service exists. All demos are listed in [DASHBOARD_IFACE.md](DASHBOARD_IFACE.md).

The MQTT contract every service follows is in [INTERFACES.md](INTERFACES.md).
