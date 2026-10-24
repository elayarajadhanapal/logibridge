# Development environment

The development setup runs on a single Windows machine: a local Mosquitto broker, the Python services, and the dashboard in a browser. Commands are for PowerShell from the repository root.

## 1. Python environment

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> **Note:** the inference container uses `python:3.11-slim` (Task D2). The local virtual environment may use a newer Python; container-specific behaviour is verified inside Docker.

## 2. Mosquitto broker

Mosquitto is installed with `winget install EclipseFoundation.Mosquitto` into `C:\Program Files\mosquitto`, which is not on `PATH`; the executables are therefore called by full path.

The project broker configuration (`deployment/mosquitto.conf`) opens TCP 1883 for the Python services and WebSockets 9001 for the dashboard:

```powershell
& "C:\Program Files\mosquitto\mosquitto.exe" -c deployment/mosquitto.conf -v
```

All project traffic can be observed with:

```powershell
& "C:\Program Files\mosquitto\mosquitto_sub.exe" -t "logibridge/#" -v
```

> **Caveat:** the Windows installer registers a `mosquitto` service that listens on 1883 only (no WebSockets). While it runs, port 1883 is taken and the project broker cannot start. It is stopped with `Stop-Service mosquitto` (administrator PowerShell) or `net stop mosquitto`.

## 3. Dashboard

`dashboard/logiedge_dashboard.html` opens directly in Chrome or Edge; it loads mqtt.js from jsdelivr, so the first connection needs internet access.

Connection: Details → Connect your code → URL `ws://localhost:9001`, truck `MH15-RF-0427` → Connect. Without any Python service running, every stage uses its built-in mock.

## 4. Smoke test

The module interface demos verify the broker, both listeners and the dashboard wiring without any service code:

```powershell
python data_pipeline/data_pipeline_dashboard_iface.py
python inference/inference_dashboard_iface.py
```

Expected result (two terminals):

- the dashboard's topic table shows ✓ for the sensor, feature, inference and model rows within a few seconds, and the corresponding stages go live;
- selecting the anomaly mode `combined` makes the temperature drift;
- clicking a model button prints `control: model -> M3` in the inference terminal.

All demos are listed in [DASHBOARD_IFACE.md](DASHBOARD_IFACE.md), section 7. The MQTT contract is specified in [INTERFACES.md](INTERFACES.md).
