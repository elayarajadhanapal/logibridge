# Development environment

The development setup runs on a single machine: a local Mosquitto broker, the Python services, and the dashboard in a browser. Commands are for PowerShell from the repository root.

## 1. One-time installation

```powershell
winget install EclipseFoundation.Mosquitto
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

> **Note:** the inference container uses `python:3.11-slim` (Task D2). The local virtual environment may use a newer Python; container-specific behaviour is verified inside Docker.

## 2. Starting the system

```powershell
python run.py
```

or double-click `run.bat`. The launcher:

1. starts a Mosquitto broker — WebSockets 9001 for the dashboard, TCP 1883 for the services (1884 when 1883 is already taken, e.g. by the Windows Mosquitto service);
2. starts every implemented service (preprocessing, inference, drift monitor, uplink agent, node monitor, simulator — modules not written yet are listed as skipped);
3. opens `dashboard/logiedge_dashboard.html`, which connects to the broker and starts by itself.

Ctrl+C (or closing the window) stops the services and the broker.

| Option | Effect |
|---|---|
| `--anomaly temp_drift` | Simulator starts in another mode (the dashboard's *Inject* selector also switches it live) |
| `--no-browser` | Does not open the dashboard |

The dashboard opens with the **Mock data (dry run)** checkbox unchecked: every edge-pipeline stage shows only what the services publish, and the banner lists the streams with no live data yet. Checking it switches to a dry run on the built-in mock, which ignores the services. See `dashboard/README.md` for both modes and the URL options.

> **Note:** an already running project broker on port 9001 (an earlier run, or one started by hand) is reused; the launcher verifies which TCP port reaches it.

## 3. Manual operation (reference)

Starting the parts individually is useful for debugging a single service.

Broker — `deployment/mosquitto.conf` opens TCP 1883 and WebSockets 9001:

```powershell
& "C:\Program Files\mosquitto\mosquitto.exe" -c deployment/mosquitto.conf -v
```

> **Caveat:** the Windows installer registers a `mosquitto` service that listens on 1883 only. While it runs, this command cannot bind 1883; it is stopped with `Stop-Service mosquitto` (administrator PowerShell). `run.py` avoids the conflict by moving to 1884.

Services — each accepts `--host` / `--port` and otherwise uses `LOGIBRIDGE_MQTT_HOST` / `LOGIBRIDGE_MQTT_PORT` (default `localhost:1883`):

```powershell
python data_pipeline/preprocessing.py
python data_pipeline/simulator.py --anomaly none
```

All project traffic:

```powershell
& "C:\Program Files\mosquitto\mosquitto_sub.exe" -p 1883 -t "logibridge/#" -v
```

## 4. Smoke test without service code

The module interface demos publish valid synthetic data on their module's topics:

```powershell
python inference/inference_dashboard_iface.py
```

Expected: the dashboard's class badge and probabilities go live; clicking a model button prints `control: model -> M3` in the terminal. All demos are listed in [DASHBOARD_IFACE.md](DASHBOARD_IFACE.md), section 7. The MQTT contract is specified in [INTERFACES.md](INTERFACES.md).
