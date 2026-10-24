# LogiEdge dashboard

Single-file visual harness for the LogiBridge pipeline (`logiedge_dashboard.html`). It runs standalone with a built-in mock of every stage, and each stage switches to live data as soon as the corresponding Python service publishes on MQTT.

| File | Purpose |
|---|---|
| `logiedge_dashboard.html` | Dashboard (no server, no build step) |
| `dashboard_api.py` | Python core of the MQTT contract used by all module interfaces — see [../docs/DASHBOARD_IFACE.md](../docs/DASHBOARD_IFACE.md) |
| `__init__.py` | Makes `dashboard` importable from the module interfaces |

## Running

`python run.py` (or `run.bat`) in the repository root starts the broker and every implemented service, then opens this page — see [../docs/SETUP.md](../docs/SETUP.md). The page needs no clicks: on load it connects to `ws://localhost:9001` (retrying until the broker is up), starts the clock and shows only live data (mock data off). The banner reports the broker connection and lists the streams with no live data yet.

The HTML file can also be opened directly in Chrome or Edge, e.g. while the stack is already running.

| URL parameter | Effect |
|---|---|
| `?mock` | Starts with mock data on |
| `?ws=ws://host:port` | Connects to another broker |
| `?selftest` | Runs the built-in test suite on load (no broker connection) |

The main screen fits one window without scrolling, sized for recording at 1440×900 or 1920×1080. It shows the route map, a status card (cargo temperature, class, with/without-edge comparison, anomaly and cellular controls) and the data path: sensors → edge node (chip selector Pi 5 / Jetson / STM32 with memory, compute and power; model selector M1 / M2 / M3 with live class probabilities, latency on the selected chip, size and fit, accuracy and Critical recall) → local storage → cellular → operations centre. Counters on each arrow show bytes generated, stored locally and sent, with a banner when a signal gap ends and the queue syncs, and an OTA banner when the model changes.

Further panels are under **Details** (key D; Esc closes): custody ribbons, full scoreboard, pipeline stages, feature table, hardware wiring, memory breakdown, models and OTA, drift, integration, self-test and event log. Space starts and pauses the run.

The live connection requires Mosquitto with a WebSocket listener on 9001 (started by `run.py`, or by hand with `deployment/mosquitto.conf`). Details → **Connect your code** shows the connection, the topic table and every message's contract check; the same tab can disconnect and reconnect to another URL. The module interface demos (e.g. `python inference/inference_dashboard_iface.py`) publish valid data on their topics and print the control messages the dashboard sends.

## Mock and live stages

| Stage | Built-in mock | Replaced by live data on |
|---|---|---|
| Sensor streams | Gaussian streams per Task C1, plus a physical plant for the incident scenarios | `…/sensors/temperature`, `/vibration`, `/door` |
| Features | MA-5 filter, 30 s / 10 s windows, the six features | `…/features` |
| Model | Transparent rules, not an MLP | `…/inference` |
| PSI | Rolling PSI on the mock confidences | `…/drift` |
| Model metrics | Placeholder numbers, flagged in the UI | `logibridge/sim/models` or CSV import |
| Cellular state | Follows the route's signal gaps | `…/link` |

A stream counts as live while messages keep arriving. It stops counting as live 5 s after its last message, or about 2.5 publish periods for the slower streams (`features` and `inference` 25 s, `drift` 150 s; `externalTimeoutBySec` in `LE.CONFIG`). While any stream is live, or mock data is off, the clock runs at 1× real time so timestamps line up.

### Mock data toggle

The **Mock data on / Mock data off** control in the status card selects whether the built-in mock fills stages that have no live data.

| | Mock data off (default) | Mock data on |
|---|---|---|
| Stage with live data | Live data | Live data |
| Stage without live data | `–` / "No data" / "waiting for …"; charts show a gap | Built-in mock |
| Banner | "Mock data OFF", listing the streams with no live data yet | "External data is driving the edge node" while any stream is live |
| Edge alerts at the operations centre | Only alerts published by `uplink_agent` | Mock alert logic, unless `uplink_agent` is online |
| CPU / power, local storage, bytes sent | Only values from `node_monitor` / `uplink_agent` | Mock estimates, unless `node_monitor` / `uplink_agent` publish |

Every page load starts with mock data off; `?mock` in the URL starts with it on. Mock data on is useful for exploring the scenarios without any Python code.

> **Note:** the toggle covers the edge pipeline. The route, signal gaps, scenario timeline, scoreboard and the "without edge" (cloud-only) comparison are part of the scenario model and stay simulated in both modes; no LogiBridge service implements them.

> **Note:** the mock rules are deliberately simple. Their numbers are not results and are not quoted in the reports.

## Code map (inside the HTML file)

1. **`LE.CONFIG`** — every tunable: setpoint, noise, window sizes, trip timeline, signal gaps, byte sizes, costs, PSI settings.
2. **`LE.HARDWARE`, `LE.PERIPHERALS`, `LE.MODELS`, `LE.SCENARIOS`** — catalogues the UI renders from.
3. **`class Sim`** — all simulation logic, no DOM. Two twins (`s.edge`, `s.cloud`) share the same physics noise and diverge only through their architecture. `step()` advances one simulated second.
4. **`LE.runSelfTests`** — tests that drive fresh `Sim` instances headlessly, plus UI wiring checks.
5. **UI layer** — `renderStatus()` and `renderFlow()` draw the main screen; one `render…()` per Details panel, all reading `sim.s`. `renderAll()` runs about eight times a second and skips the Details panels while that overlay is closed. Compute and power come from `Sim._chipTick()`, an estimate driven by the per-board numbers in `LE.HARDWARE` (`idleW`, `basePct`, `sampleMs`, `featMs`).
6. **`window.LogiEdge`** — the public JavaScript API; the MQTT bridge also goes through `push(stream, msg)`.

## Extending the UI

A UI addition follows three steps:

1. State lives in `Sim` (a field on `this.s` or on a twin) and is updated inside `step()` or the owning stage, with an event emitted if other parts react to it.
2. Markup goes into the shell: a tab button plus `<div class="tabpane" id="tab-name">`, or a block inside an existing panel.
3. A `renderName()` function reads `sim.s`, fills that markup, and is registered in the tab map inside `renderAll()`.

Each addition is covered by a test in `LE.runSelfTests` that creates a fresh `Sim`, runs it, and asserts on the new state; DOM-dependent tests go in the browser-only block at the bottom.

A new external stream requires its topic in `TOPICS`, a validator in `SCHEMA`, an example in `EXAMPLES`, and a branch in `Sim.ext()`, plus the matching entry in `dashboard_api.py` (`STREAMS`).

## Message contract

The full contract, including `node/metrics`, `storage`, `uplink/sync`, `alerts`, `model/active`, `status/<service>` and the `control` commands, is specified in [../docs/INTERFACES.md](../docs/INTERFACES.md). Summary:

| Stream | Payload |
|---|---|
| temperature, vibration | `{"ts": float, "value": float}` |
| door | `{"ts": float, "state": "OPEN" \| "CLOSE"}` |
| features | `{"ts": float, "raw": [6], "norm": [6]}` (either or both) |
| inference | `{"ts": float, "class": 0\|1\|2, "probs": [3], "latency_ms": float, "model": "M1"\|"M2"\|"M3"}` |
| drift | `{"ts": float, "psi": float}` |
| link | `{"cellular": bool}` |
| gps | `{"lat": float, "lon": float}` |
| models | `{"M2": {"sizeKB":…, "latencyMs":…, "p95Ms":…, "accuracy":…, "recallC2":…, "energyMJ":…}}` |
| control (dashboard → services) | `{"ts": float, "anomaly": "none\|temp_drift\|vibration\|combined"}` or `{"ts": float, "model": "M2"}` |

The dashboard accepts `ts` as optional; the Python services always include it. The inference topic follows the problem statement (`logibridge/trucks/{truck_id}/inference`); the other topic names are editable in the dashboard's Connect tab.
