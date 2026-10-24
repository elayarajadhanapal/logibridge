# Connecting your module to the dashboard

You never write MQTT code. Each module has one file, `<module>_dashboard_iface.py`, with plain methods. Call them from your code and your stage appears live on the dashboard.

## 1. Find your file

| Folder | Iface file | Class / function | Used by |
|---|---|---|---|
| `data_pipeline/` | `data_pipeline_dashboard_iface.py` | `SimulatorDashboard` | `simulator.py` |
| | | `PreprocessingDashboard` | `preprocessing.py` |
| `inference/` | `inference_dashboard_iface.py` | `InferenceDashboard` | `inference_service.py` |
| `monitoring/` | `monitoring_dashboard_iface.py` | `DriftMonitorDashboard` | `drift_monitor.py` |
| `edge_runtime/` | `edge_runtime_dashboard_iface.py` | `UplinkAgentDashboard`, `NodeMonitorDashboard` | `uplink_agent.py`, `node_monitor.py` |
| `optimisation/` | `optimisation_dashboard_iface.py` | `publish_benchmark_csv()` | `benchmark.py` |

`training/` and `deployment/` have no iface: they run offline and the dashboard shows nothing from them.

## 2. Use it — three steps

```python
from data_pipeline_dashboard_iface import SimulatorDashboard   # 1. import (same folder)

dash = SimulatorDashboard()                                     # 2. create once at start-up
dash.on_anomaly_command(lambda mode: print("switch to", mode))  #    optional: dashboard commands

while running:
    dash.temperature(value_c, ts)                               # 3. send your results
dash.close()                                                    #    on exit
```

The docstring at the top of each iface file lists every method. Arguments are plain numbers, strings and lists; numpy values are fine.

| Method kind | Meaning |
|---|---|
| `dash.<stream>(...)` | Send a result (to the dashboard **and** to any module that listens) |
| `dash.on_<input>(callback)` | Receive what an upstream module sent, e.g. preprocessing gets sensor readings |
| `dash.on_<x>_command(callback)` | Receive a button press from the dashboard (anomaly mode, model, cellular) |

Callbacks run on a background thread. Keep them tiny — append to a list or `queue.Queue`, then do the real work in your main loop.

## 3. See it before you write code

Every iface file runs a demo with fake data:

```powershell
python data_pipeline/data_pipeline_dashboard_iface.py     # sensors + features
python inference/inference_dashboard_iface.py             # classes + model switch
python monitoring/monitoring_dashboard_iface.py           # PSI rising and recovering
python edge_runtime/edge_runtime_dashboard_iface.py       # storage, signal gaps, alerts, CPU/power
python optimisation/optimisation_dashboard_iface.py       # benchmark numbers (retained)
```

Start the broker and dashboard first ([SETUP.md](SETUP.md)). Then replace the demo with your real module.

## 4. When something is wrong

- **`ValueError: inference.probs must sum to 1, got 1.300`** — your payload breaks the contract. The message names the field. Fix your data; the dashboard would have rejected it anyway. NaN and inf are rejected too (a constant window gives NaN kurtosis — handle it in your code).
- **`WARNING: no MQTT broker at localhost:1883`** — Mosquitto is not running. Your code keeps working; messages are dropped until the broker appears, then it reconnects by itself.
- **No broker at all?** Set `$env:LOGIBRIDGE_IFACE="print"` to print every message as JSON, or `"off"` to only validate. Useful for dataset generation and unit tests.
- **Different broker:** `$env:LOGIBRIDGE_MQTT_HOST` / `$env:LOGIBRIDGE_MQTT_PORT`, or `SimulatorDashboard(host=..., port=...)`. Different truck: `SimulatorDashboard(truck_id="...")`.

## 5. How it fits together

```
your_module.py ──calls──> <module>_dashboard_iface.py ──> dashboard/dashboard_api.py ──MQTT 1883──> Mosquitto
   (your logic)            (plain methods, ~60 lines)       (envelope, validation,            │
                                                              status + last will, control)    ├──WS 9001──> dashboard HTML
                                                                                              └──1883────> downstream modules
```

- `dashboard/dashboard_api.py` is the only file that knows topics, QoS, retain flags and field rules. Change the contract there and in [INTERFACES.md](INTERFACES.md), nowhere else.
- Every service automatically shows as a live badge on the dashboard (`status/<service>`), and turns offline if it crashes.
- Tests: `python -m pytest tests -v` (starts its own broker on port 18830).
- Docker (inference): build from the repository root so `dashboard/` is copied into the image next to `inference/`.
