# LogiBridge MQTT contract

Specification of the topics, payloads and commands exchanged between the LogiBridge services and the dashboard (`dashboard/logiedge_dashboard.html`). The contract is implemented in `dashboard/dashboard_api.py` and exposed to services through the module interfaces described in [DASHBOARD_IFACE.md](DASHBOARD_IFACE.md).

## 1. Transport

| Client | Protocol | Address |
|---|---|---|
| Python services | MQTT over TCP | `localhost:1883` |
| Dashboard (browser) | MQTT over WebSockets | `ws://localhost:9001` |

Both listeners belong to the same Mosquitto broker (`deployment/mosquitto.conf`); services and dashboard never communicate directly.

Every dashboard stage has a built-in mock. When a service publishes on a stage's topic, the dashboard displays that data instead; if the messages stop for 5 s (25 s for `features` and `inference`, 150 s for `drift`), the stage counts as having no live data. In the dashboard's default live mode such a stage shows "no data"; in the dry-run mode (**Mock data** checked) the dashboard ignores service data and runs entirely on its mock. While any sensor, feature or inference stream is external, the dashboard clock is locked to 1× real time so timestamps line up.

The dashboard owns the scenario (route timing, signal gaps, anomaly injection, model choice) and announces it as commands on the `control` topic. Services report the resulting state on their own topics; the dashboard does not assume a command succeeded until the report arrives (for example `model/active` after a model switch).

## 2. Message envelope

Topic prefix: `logibridge/trucks/{truck_id}/`. Default truck ID: `MH15-RF-0427` (configurable in the dashboard's Connect tab).

Payloads are UTF-8 JSON objects. Every message carries the envelope below plus its stream-specific fields:

| Field | Type | Meaning |
|---|---|---|
| `v` | int | Schema version, currently `1` |
| `truck_id` | string | Same as in the topic |
| `ts` | float | Unix seconds, **data time** (when the reading or event happened, not when it was sent) |
| `seq` | int | Increments by 1 per message from a service; lets receivers detect loss and duplicates |
| `src` | string | Publishing service name, e.g. `"simulator"` |

Unknown fields are ignored by the dashboard, so payloads can be extended. A message is rejected only if a required field is missing or has the wrong type; rejected messages appear in Details → Event log and as ✗ in the Connect tab.

## 3. Client conventions

| Setting | Value | Rationale |
|---|---|---|
| Client ID | `logiedge-<service>-<truck_id>` | Stable identity for persistent sessions and logs |
| Keepalive | 10 s | Broker detects a dead service within ~15 s |
| Last will | topic `status/<service>`, payload `{"online": false}`, QoS 1, retained | Dashboard marks the stage offline after a crash |
| On connect | publish `status/<service>` `{"online": true}`, QoS 1, retained | Re-sent after every automatic reconnect |
| On clean exit | publish `{"online": false}` retained, then disconnect | A clean disconnect does not trigger the last will |

## 4. Topic table

Topics are relative to `logibridge/trucks/{truck_id}/` unless they start with `logibridge/`.

| Topic | Publisher | Required fields (plus envelope) | QoS | Retain | Rate | Dashboard effect |
|---|---|---|---|---|---|---|
| `sensors/temperature` | simulator | `value` (°C, float) | 0 | no | 1 Hz | Sensor card, temperature trend, cargo reading |
| `sensors/vibration` | simulator | `value` (g RMS, float) | 0 | no | 0.5 Hz | Sensor card, vibration trend |
| `sensors/door` | simulator | `state`: `"OPEN"` or `"CLOSE"` | 1 | no | on event | Door state and timeline |
| `features` | preprocessing | `window_start` (float), `raw` (6 floats); optional `norm` (6 floats) | 0 | no | every 10 s | Feature table; feeds the mock model when no inference service runs |
| `inference` | inference | `class` (0/1/2), `probs` (3 floats, sum 1), `latency_ms`, `model` | 1 | no | every 10 s | Class badge, probability bars, latency |
| `model/active` | inference | `model` (`M1`/`M2`/`M3`), `size_kb`; optional `sha256` | 1 | yes | on load | Confirms a model switch, OTA banner |
| `drift` | drift_monitor | `psi` (float); optional `bins` (4 floats), `n` | 1 | no | every 60 s | PSI chart and drift alerts |
| `alerts` | uplink_agent | `class` (0 clear / 1 / 2), `msg` (string), `raised_ts` (float) | 1 | no | on event | Operations-centre list; lateness = `ts − raised_ts` |
| `storage` | uplink_agent | `stored_bytes`, `queued_bytes`, `sent_bytes` (ints); optional `queued_records` | 1 | yes | 1 Hz | Local storage card, bytes sent, operations received |
| `uplink/sync` | uplink_agent | `records`, `bytes` (ints); optional `gap_s` | 1 | no | on reconnect | "Signal back · syncing …" banner |
| `link` | uplink_agent | `cellular` (bool) | 1 | yes | on change | Display only; the route decides signal |
| `node/metrics` | node_monitor | `cpu_pct`, `power_w` (floats); optional `ram_used_kb`, `ram_total_kb`, `power_src` (`"estimate"`/`"measured"`) | 0 | no | 1 Hz | Edge-node compute, memory and power meters |
| `status/<service>` | every service | `online` (bool) | 1 | yes | on connect, LWT | Live-service badges |
| `logibridge/sim/models` | benchmark | `{"M1": {...}, "M2": {...}, "M3": {...}}` with any of `sizeKB`, `latencyMs`, `p95Ms`, `accuracy`, `recallC2`, `energyMJ` | 1 | yes | once | Model metrics replace placeholders |
| `control` | **dashboard** | one of `anomaly`, `model`, `cellular` (section 6) | 1 | no | on user action or route event | — |

Service names used in `status/<service>`: `simulator`, `preprocessing`, `inference`, `drift_monitor`, `uplink_agent`, `node_monitor`.

## 5. Topics per service

| Service | Publishes | Subscribes |
|---|---|---|
| `simulator.py` | `sensors/temperature`, `sensors/vibration`, `sensors/door`, `status/simulator` | `control` (`anomaly`) |
| `preprocessing.py` | `features`, `status/preprocessing` | `sensors/temperature`, `sensors/vibration`, `sensors/door` |
| `inference_service.py` | `inference`, `model/active`, `status/inference` | `features`, `control` (`model`) |
| `drift_monitor.py` | `drift`, `status/drift_monitor` | `inference` |
| `uplink_agent.py` | `storage`, `uplink/sync`, `alerts`, `link`, `status/uplink_agent` | `inference`, `control` (`cellular`) |
| `node_monitor.py` | `node/metrics`, `status/node_monitor` | — |
| `benchmark.py` | `logibridge/sim/models` | — |

Notes:

- `ts` on sensor topics is the reading's own time. When the simulator runs faster than real time (dataset generation), `ts` remains spaced 1 s apart in data time.
- When `training_stats.npy` is unavailable, `features` carries `raw` only; statistics are never computed from live data (Task C2).
- `[LOGIBRIDGE DRIFT ALERT] PSI=x.xxx` is a console output of `drift_monitor.py` (Task E1) in addition to the `drift` topic.
- Once `status/uplink_agent` is online, the dashboard stops raising its own edge alerts, so the operations panel shows exactly what the agent delivered.
- Laptop power cannot be measured; `node/metrics` carries an estimate with `power_src: "estimate"`.
- `logibridge/sim/models` can alternatively be supplied by pasting `benchmark_results.csv` into the dashboard's Connect tab.

## 6. Commands on `control`

Published by the dashboard at QoS 1. Every command is idempotent: receiving the same command twice has no additional effect.

| Payload | Handled by | Behaviour |
|---|---|---|
| `{"anomaly": "none" \| "temp_drift" \| "vibration" \| "combined"}` | simulator | Switches mode immediately without restart, same semantics as `--anomaly`. Switching to `none` resets the accumulated drift offset so PSI can recover. |
| `{"model": "M1" \| "M2" \| "M3"}` | inference | Loads the model file, then publishes `model/active`. On a failed load the previous model stays active and `model/active` is not published. |
| `{"cellular": true \| false}` | uplink_agent | Link up or down. While down, records are queued instead of sent; on `true` the queue is flushed and `uplink/sync` is published. |

The dashboard sends `cellular` automatically as the truck enters and leaves each signal gap on the route, and when the On/Off buttons are pressed.

## 7. Contract verification

1. Mosquitto running with both listeners (`deployment/mosquitto.conf`, see [SETUP.md](SETUP.md)).
2. Dashboard → Details → Connect your code → Connect.
3. With a service running, its rows in the topic table show ✓ and a recent "last seen". ✗ indicates a missing or wrongly typed field; Details → Event log shows the rejected payload.
4. Raw traffic: `mosquitto_sub -t "logibridge/#" -v`.
5. Without any service: the demo in each `<module>_dashboard_iface.py` publishes valid synthetic data on that module's topics and prints the `control` messages it receives ([DASHBOARD_IFACE.md](DASHBOARD_IFACE.md), section 7).

## 8. Changing the contract

Topic names are editable in the dashboard's Connect tab without code changes. A new stream requires changes in three places: the `STREAMS` table in `dashboard/dashboard_api.py`, this document, and in the dashboard HTML the `TOPICS`, `SCHEMA` and `EXAMPLES` tables plus a branch in `Sim.ext()` and a self-test (see `dashboard/README.md`).
