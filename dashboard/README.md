# LogiEdge dashboard

A single-file visual harness for the LogiEdge pipeline. It runs on its own with a built-in mock of every stage, and each stage hands over to your real Python code as soon as that code publishes on MQTT.

## Run it

Open `logiedge_dashboard.html` in Chrome or Edge. No server, no build step. Add `?selftest` to the URL to run the test suite on load.

The main screen fits one window with no scrolling, sized for recording at 1440×900 or 1920×1080. It shows the route map, a status card (cargo temperature, class, with/without-edge comparison, anomaly and cellular controls) and the data path: sensors → edge node (chip buttons Pi 5 / Jetson / STM32 with memory, compute and power; model buttons M1 / M2 / M3 with live class probabilities, latency on the chosen chip, size and fit, accuracy and Critical recall) → local storage → cellular → operations centre. Counters on each arrow show bytes generated, copied locally and sent, with floating +bytes labels as data moves, a banner when a signal gap ends and the queue syncs, and an OTA banner on the cellular link when you switch models.

Everything else — custody ribbons, full scoreboard, pipeline stages, feature table, hardware wiring, memory breakdown, models and OTA, drift, integration, self-test, event log — is under **Details** (or press D; Esc closes). Space starts and pauses the run.

To connect your Python services, Mosquitto needs a WebSocket listener next to the normal TCP one. Example `mosquitto.conf`:

```
listener 1883
listener 9001
protocol websockets
allow_anonymous true
```

The repo version is `deployment/mosquitto.conf`; start it as described in `docs/SETUP.md`, then in the dashboard open **Connect your code** and press **Connect**. Run a module demo such as `python inference/inference_dashboard_iface.py` to see its topics show ✓, and click a model button to see the control message arrive in the script (all demos: `docs/DASHBOARD_IFACE.md`).

## What is mock and what is yours

| Stage | Built-in mock | Replaced when you publish |
|---|---|---|
| Sensor streams | Gaussian streams per Task C1, plus a physical plant for the incident scenarios | `…/sensors/temperature`, `/vibration`, `/door` |
| Features | MA-5 filter, 30 s / 10 s windows, the six features | `…/features` |
| Model | Transparent rules, not an MLP | `…/inference` |
| PSI | Rolling PSI on the mock confidences | `…/drift` |
| Model metrics | Placeholder numbers, flagged in the UI | `logibridge/sim/models` or CSV import |
| Cellular state | Follows the route's signal gaps | `…/link` |

A stream counts as external while messages keep arriving; five seconds after the last one, the mock resumes. While any sensor, feature or inference stream is external, speed locks to 1× so timestamps line up.

The mock rules are deliberately simple and readable. They are not your model and their numbers are not results; never quote them in the report.

## Code map (inside the one HTML file)

1. **`LE.CONFIG`** — every tunable: setpoint, noise, window sizes, trip timeline, signal gaps, byte sizes, costs, PSI settings. Change numbers here first.
2. **`LE.HARDWARE`, `LE.PERIPHERALS`, `LE.MODELS`, `LE.SCENARIOS`** — catalogues the UI renders from.
3. **`class Sim`** — all simulation logic, no DOM. Two twins (`s.edge`, `s.cloud`) share the same physics noise and diverge only through their architecture. `step()` advances one simulated second.
4. **`LE.runSelfTests`** — tests that drive fresh `Sim` instances headlessly, plus UI wiring checks.
5. **UI layer** — `renderStatus()` and `renderFlow()` draw the main screen; one `render…()` per Details panel. All read `sim.s`. `renderAll()` runs about eight times a second and skips the Details panels while that overlay is closed. Compute and power come from `Sim._chipTick()`, an estimate driven by the per-board numbers in `LE.HARDWARE` (`idleW`, `basePct`, `sampleMs`, `featMs`).
6. **`window.LogiEdge`** — the public API and the MQTT bridge both go through `push(stream, msg)`.

## Adding something to the UI

The pattern is always the same three steps.

1. Put the state in `Sim` (a field on `this.s` or on a twin) and update it inside `step()` or the stage that owns it. Emit an event if other parts need to react.
2. Add markup to the shell: a new tab button plus a `<div class="tabpane" id="tab-yourname">`, or a block inside an existing panel.
3. Write `renderYourname()` that reads `sim.s` and fills that markup, and register it in the tab map inside `renderAll()`.

Then add a test in `LE.runSelfTests` that creates a fresh `Sim`, runs it, and asserts on the state you added. If the test needs the DOM, put it in the browser-only block at the bottom.

To accept a new external stream: add its topic to `TOPICS`, a validator to `SCHEMA`, an example to `EXAMPLES`, and a branch in `Sim.ext()`.

## Message contract

The full contract, including the new topics (`node/metrics`, `storage`, `uplink/sync`, `alerts`, `model/active`, `status/<service>`) and what each service must do with `control` commands, is in `docs/INTERFACES.md`. The table below is the short version.

All payloads are JSON. `ts` is optional for the dashboard but your own services should include it.

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
| control (UI → you) | `{"ts": float, "anomaly": "none\|temp_drift\|vibration\|combined"}` or `{"ts": float, "model": "M2"}` |

The inference topic follows the problem statement (`logibridge/trucks/{truck_id}/inference`). The other topic names are editable in the dashboard, so they can follow whatever your MQTT architecture document decides.
