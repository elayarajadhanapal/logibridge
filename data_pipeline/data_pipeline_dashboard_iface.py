"""
data_pipeline_dashboard_iface.py — MQTT interface for simulator.py and preprocessing.py.

The sensor and feature topics are both the dashboard feed and the pipeline's own
data bus: preprocessing reads the simulator's readings through this file too.

simulator.py:
    from data_pipeline_dashboard_iface import SimulatorDashboard
    dash = SimulatorDashboard()
    dash.on_anomaly_command(lambda mode: print("dashboard asked for", mode))
    dash.temperature(4.12, ts)      # every 1 s
    dash.vibration(0.46, ts)        # every 2 s
    dash.door("OPEN", ts)           # on change
    dash.close()                    # on exit

preprocessing.py:
    from data_pipeline_dashboard_iface import PreprocessingDashboard
    dash = PreprocessingDashboard()
    dash.on_temperature(lambda value, ts: ...)
    dash.on_vibration(lambda value, ts: ...)
    dash.on_door(lambda state, ts: ...)
    dash.features(raw6, norm6, window_start=t0, ts=t1)   # every 10 s
    dash.close()

Callbacks run on the MQTT network thread; the usual pattern is to append to a list or
queue and process the data in the main loop.

Demo with synthetic data:   python data_pipeline/data_pipeline_dashboard_iface.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root
from dashboard.dashboard_api import DEFAULT_TRUCK_ID, DashboardLink  # noqa: E402


class SimulatorDashboard:
    """Publishes the three sensor streams; receives anomaly-mode commands."""

    def __init__(self, truck_id=DEFAULT_TRUCK_ID, **link_options):
        self.link = DashboardLink("simulator", truck_id, **link_options)

    def temperature(self, value_c, ts=None):
        """Cargo temperature in °C. `ts` = time of the reading (Unix seconds)."""
        self.link.publish("temperature", {"value": value_c}, ts)

    def vibration(self, rms_g, ts=None):
        """Compressor vibration RMS in g."""
        self.link.publish("vibration", {"value": rms_g}, ts)

    def door(self, state, ts=None):
        """Door event: "OPEN" or "CLOSE"."""
        self.link.publish("door", {"state": state}, ts)

    def on_anomaly_command(self, callback):
        """callback(mode) with mode in none / temp_drift / vibration / combined."""
        self.link.on_control("anomaly", callback)

    def close(self):
        self.link.close()


class PreprocessingDashboard:
    """Receives sensor readings; publishes the 6-value feature vector per window."""

    def __init__(self, truck_id=DEFAULT_TRUCK_ID, **link_options):
        self.link = DashboardLink("preprocessing", truck_id, **link_options)

    def on_temperature(self, callback):
        """callback(value_c, ts) for every temperature reading."""
        self.link.subscribe("temperature", lambda m: callback(m["value"], m["ts"]))

    def on_vibration(self, callback):
        """callback(rms_g, ts) for every vibration reading."""
        self.link.subscribe("vibration", lambda m: callback(m["value"], m["ts"]))

    def on_door(self, callback):
        """callback(state, ts) for every door event."""
        self.link.subscribe("door", lambda m: callback(m["state"], m["ts"]))

    def features(self, raw, norm=None, window_start=None, ts=None):
        """
        raw  = [temp_mean, temp_std, temp_roc_c_per_min, vib_rms, vib_peak, vib_kurtosis]
        norm = the same 6 values after normalising with training_stats.npy (None if no stats)
        window_start / ts = data time of the window's first / last sample.
        """
        if window_start is None:
            window_start = (ts if ts is not None else 0.0) - 30.0
        self.link.publish("features", {"window_start": window_start, "raw": raw, "norm": norm}, ts)

    def close(self):
        self.link.close()


def _demo(seconds=60):
    """Publish plausible fake data so the dashboard's sensor and feature stages go live."""
    import random
    import time

    sim, pre = SimulatorDashboard(), PreprocessingDashboard()
    mode = {"value": "none"}
    sim.on_anomaly_command(lambda m: (mode.update(value=m), print("control: anomaly ->", m)))
    received = {"temperature": 0}
    pre.on_temperature(lambda v, ts: received.update(temperature=received["temperature"] + 1))
    drift, door_open = 0.0, False
    for i in range(seconds):
        now = time.time()
        drift = drift + 0.08 if mode["value"] in ("temp_drift", "combined") else 0.0
        sim.temperature(random.gauss(4.0, 0.3) + drift, now)
        if i % 2 == 0:
            vib = (1.2, 0.15) if mode["value"] in ("vibration", "combined") else (0.45, 0.05)
            sim.vibration(random.gauss(*vib), now)
        if i % 25 == 24:
            door_open = not door_open
            sim.door("OPEN" if door_open else "CLOSE", now)
        if i % 10 == 9:
            raw = [4.0 + drift, 0.3, 4.8 if drift else 0.0, 0.45, 0.6, 3.0]
            pre.features(raw, [0.0] * 6, window_start=now - 30, ts=now)
        time.sleep(1)
    print(f"demo done; preprocessing received {received['temperature']} temperature readings back")
    sim.close()
    pre.close()


if __name__ == "__main__":
    _demo(int(sys.argv[1]) if len(sys.argv) > 1 else 60)
