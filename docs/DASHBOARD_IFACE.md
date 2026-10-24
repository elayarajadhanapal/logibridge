# Dashboard interface API

Python API through which LogiBridge services exchange data with each other and with the dashboard (`dashboard/logiedge_dashboard.html`). Services call plain methods; topic names, QoS, payload envelope, validation, liveness and command handling are implemented once in `dashboard/dashboard_api.py`.

## 1. Architecture

```
service.py ──> <module>_dashboard_iface.py ──> dashboard/dashboard_api.py ──MQTT 1883──> Mosquitto
               (module-specific methods)       (contract, envelope,                        │
                                                validation, status, control)               ├──WS 9001──> dashboard
                                                                                           └──1883────> downstream services
```

| Layer | File | Responsibility |
|---|---|---|
| Core | `dashboard/dashboard_api.py` | `DashboardLink` class and the `STREAMS` contract table — the single definition of topics, QoS, retain flags and field rules |
| Module interface | `<module>/<module>_dashboard_iface.py` | Thin classes exposing one method per stream the module publishes or consumes |
| Contract reference | [INTERFACES.md](INTERFACES.md) | Topic tree and payload specification |

Sensor, feature and inference topics are both the dashboard feed and the pipeline's data path: a downstream service (e.g. preprocessing) receives upstream data through the same interface.

## 2. Module interfaces

| Module | Interface file | Class / function | Service |
|---|---|---|---|
| `data_pipeline/` | `data_pipeline_dashboard_iface.py` | `SimulatorDashboard` | `simulator.py` |
| | | `PreprocessingDashboard` | `preprocessing.py` |
| `inference/` | `inference_dashboard_iface.py` | `InferenceDashboard` | `inference_service.py` |
| `monitoring/` | `monitoring_dashboard_iface.py` | `DriftMonitorDashboard` | `drift_monitor.py` |
| `edge_runtime/` | `edge_runtime_dashboard_iface.py` | `UplinkAgentDashboard`, `NodeMonitorDashboard` | `uplink_agent.py`, `node_monitor.py` |
| `optimisation/` | `optimisation_dashboard_iface.py` | `publish_benchmark_rows()`, `publish_benchmark_csv()` | `benchmark.py` |

`training/` and `deployment/` have no interface; they run offline and publish nothing to the dashboard.

## 3. Common behaviour

### 3.1 Constructor

Every class takes the same arguments:

```python
SimulatorDashboard(truck_id="MH15-RF-0427", host="localhost", port=1883, connect_timeout=3.0)
```

| Parameter | Default | Description |
|---|---|---|
| `truck_id` | `"MH15-RF-0427"` | Topic prefix `logibridge/trucks/{truck_id}/` |
| `host`, `port` | `LOGIBRIDGE_MQTT_HOST` / `LOGIBRIDGE_MQTT_PORT`, else `localhost:1883` | Broker address |
| `connect_timeout` | `3.0` | Seconds the constructor waits for the first connection before continuing in the background |

On construction the service connects, publishes retained `status/<service> {"online": true}` and registers a last will `{"online": false}`. `close()` publishes `{"online": false}` and disconnects.

### 3.2 Method conventions

| Form | Direction | Behaviour |
|---|---|---|
| `obj.<stream>(...)` | publish | Validates the fields, adds the envelope, publishes with the contract's QoS and retain flag |
| `obj.on_<stream>(callback)` | consume | Calls `callback` for every message another service publishes on that stream |
| `obj.on_<command>_command(callback)` | dashboard command | Calls `callback(value)` when the dashboard sends that command on `control` |

`ts` arguments are data time in Unix seconds (time of the reading or event, not of sending); default is the current time. numpy scalars and arrays are accepted wherever numbers or lists are.

### 3.3 Modes

Selected by the environment variable `LOGIBRIDGE_IFACE`:

| Value | Behaviour |
|---|---|
| `mqtt` (default) | Publishes to and receives from the broker |
| `print` | Prints each message as `<topic> <json>`; no broker required; callbacks never fire |
| `off` | Validates payloads only; sends nothing |

## 4. API reference

### 4.1 `SimulatorDashboard` — service `simulator`

| Method | Topic | Parameters |
|---|---|---|
| `temperature(value_c, ts=None)` | `sensors/temperature` | Cargo temperature, °C |
| `vibration(rms_g, ts=None)` | `sensors/vibration` | Compressor vibration RMS, g |
| `door(state, ts=None)` | `sensors/door` | `"OPEN"` or `"CLOSE"` |
| `on_anomaly_command(callback)` | `control` | `callback(mode)`, mode ∈ `none`, `temp_drift`, `vibration`, `combined` |

### 4.2 `PreprocessingDashboard` — service `preprocessing`

| Method | Topic | Parameters |
|---|---|---|
| `on_temperature(callback)` | `sensors/temperature` | `callback(value_c, ts)` |
| `on_vibration(callback)` | `sensors/vibration` | `callback(rms_g, ts)` |
| `on_door(callback)` | `sensors/door` | `callback(state, ts)` |
| `features(raw, norm=None, window_start=None, ts=None)` | `features` | `raw`: 6 values `[temp_mean, temp_std, temp_roc_c_per_min, vib_rms, vib_peak, vib_kurtosis]`; `norm`: the same after normalisation with `training_stats.npy` (omitted when `None`); `window_start` / `ts`: data time of the window's first / last sample (`window_start` defaults to `ts − 30`) |

### 4.3 `InferenceDashboard` — service `inference`

| Method | Topic | Parameters |
|---|---|---|
| `on_features(callback)` | `features` | `callback(raw, norm, ts)`; `norm` is `None` when absent |
| `on_model_command(callback)` | `control` | `callback(model_id)`, model_id ∈ `M1`, `M2`, `M3` |
| `inference(cls, probs, latency_ms, model, ts=None)` | `inference` | `cls` ∈ 0 Normal, 1 Warning, 2 Critical; `probs`: 3 softmax outputs summing to 1; `latency_ms`; `model` ∈ `M1`–`M3`; `ts`: window end time |
| `model_active(model, size_kb, sha256=None)` | `model/active` (retained) | Confirms a successfully loaded model |

> **Note:** the dashboard treats a model switch as complete only when `model/active` arrives. `model_active()` is therefore published only after a successful load.

### 4.4 `DriftMonitorDashboard` — service `drift_monitor`

| Method | Topic | Parameters |
|---|---|---|
| `on_inference(callback)` | `inference` | `callback(cls, probs, ts)` |
| `drift(psi, bins=None, n=None, ts=None)` | `drift` | `psi`: current PSI; `bins`: 4 current bin fractions; `n`: number of inferences in the rolling window |

> **Note:** the console line `[LOGIBRIDGE DRIFT ALERT] PSI={value:.3f}` required by Task E1 is printed by `drift_monitor.py`, not by the interface.

### 4.5 `UplinkAgentDashboard` — service `uplink_agent`

| Method | Topic | Parameters |
|---|---|---|
| `on_inference(callback)` | `inference` | `callback(cls, probs, ts)` |
| `on_cellular_command(callback)` | `control` | `callback(up)`; `False` = truck entered a signal gap, `True` = signal restored |
| `link_state(cellular)` | `link` (retained) | Link state the agent is acting on |
| `storage(stored_bytes, queued_bytes, sent_bytes, queued_records=None)` | `storage` (retained) | Integer byte counters of the local log |
| `alert(cls, msg, raised_ts, ts=None)` | `alerts` | Alert delivered to operations; `cls` 0 = all clear; `ts` = delivery time |
| `sync(records, bytes_sent, gap_s=None)` | `uplink/sync` | Queue flush after signal returns |

> **Note:** while `status/uplink_agent` is online, the dashboard stops generating its own alerts and displays only those delivered through `alert()`.

### 4.6 `NodeMonitorDashboard` — service `node_monitor`

| Method | Topic | Parameters |
|---|---|---|
| `metrics(cpu_pct, power_w, ram_used_kb=None, ram_total_kb=None, power_src="estimate")` | `node/metrics` | `power_src` ∈ `"estimate"` (E = P × t from TDP), `"measured"` |

### 4.7 Benchmark functions — `optimisation_dashboard_iface.py`

| Function | Topic | Parameters |
|---|---|---|
| `publish_benchmark_rows(rows)` | `logibridge/sim/models` (retained) | List of dicts keyed by CSV column; returns the published metrics |
| `publish_benchmark_csv(path)` | same | Path to `benchmark_results.csv` |

CSV columns: `variant, mean_latency_ms, p95_latency_ms, size_kb, accuracy, energy_mj, class2_recall` (accuracy and recall in percent). These map to the dashboard metrics `latencyMs, p95Ms, sizeKB, accuracy, energyMJ, recallC2`. The message is retained, so a dashboard opened later still receives it; it publishes no `status/` topic.

## 5. Errors

| Condition | Behaviour |
|---|---|
| Missing field, wrong type, value outside the allowed set, wrong vector length, probabilities not summing to 1, NaN or infinity | `ValueError` naming the stream and field, e.g. `inference.probs must sum to 1, got 1.300` |
| Broker unreachable at start-up | Warning `no MQTT broker at host:port`; the service continues, messages are dropped until the background reconnect succeeds |
| Exception inside a callback | Printed with the callback name; other callbacks and message delivery continue |
| Invalid `control` value (e.g. unknown anomaly mode) | Ignored and printed; callbacks are not called |

## 6. Notes and caveats

- **Callback thread.** Callbacks run on the MQTT network thread. Long work inside a callback delays all message delivery for that service; the usual pattern is to append to a list or `queue.Queue` and process in the main loop.
- **NaN features.** Kurtosis of a constant window is NaN, which the validator rejects; such windows need handling before `features()` is called.
- **paho-mqtt version.** The core requires paho-mqtt ≥ 2.0 (`CallbackAPIVersion.VERSION2`); 1.x raises `AttributeError` on import.
- **Client ID.** The client ID is `logiedge-<service>-<truck_id>`. Two processes with the same service and truck disconnect each other.
- **Docker.** `inference_service.py` imports `dashboard/dashboard_api.py`, so the image is built with the repository root as build context.
- **Import path.** Each interface file adds the repository root to `sys.path`, so services run as `python <module>/<service>.py` from any working directory.

## 7. Demo entry points

Each interface file runs a self-contained demo with synthetic data, which brings the corresponding dashboard stages live without any service code:

| Command | Dashboard stages |
|---|---|
| `python data_pipeline/data_pipeline_dashboard_iface.py [seconds]` | Sensors, features; reacts to the anomaly selector |
| `python inference/inference_dashboard_iface.py [seconds]` | Class badge, probabilities, latency; reacts to model buttons |
| `python monitoring/monitoring_dashboard_iface.py [seconds]` | PSI rising above 0.25 and recovering below 0.10 |
| `python edge_runtime/edge_runtime_dashboard_iface.py [seconds]` | Local storage, signal gaps and sync, alerts, CPU and power |
| `python optimisation/optimisation_dashboard_iface.py` | Model metrics (sample values, not results) |

Broker and dashboard setup: [SETUP.md](SETUP.md).
