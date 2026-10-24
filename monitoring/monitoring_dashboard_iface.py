"""
monitoring_dashboard_iface.py — MQTT interface for drift_monitor.py.

    from monitoring_dashboard_iface import DriftMonitorDashboard
    dash = DriftMonitorDashboard()
    dash.on_inference(lambda cls, probs, ts: ...)   # every inference result
    dash.drift(psi=0.31, bins=[0.7, 0.1, 0.1, 0.1], n=100)   # every 60 s
    dash.close()

The console line  [LOGIBRIDGE DRIFT ALERT] PSI={value:.3f}  required by Task E1
is printed by drift_monitor.py itself; this file only feeds the dashboard.

Callbacks run on the MQTT network thread; long callbacks delay message delivery.

Demo with synthetic data:   python monitoring/monitoring_dashboard_iface.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root
from dashboard.dashboard_api import DEFAULT_TRUCK_ID, DashboardLink  # noqa: E402


class DriftMonitorDashboard:
    def __init__(self, truck_id=DEFAULT_TRUCK_ID, **link_options):
        self.link = DashboardLink("drift_monitor", truck_id, **link_options)

    def on_inference(self, callback):
        """callback(cls, probs, ts) for every inference the inference service publishes."""
        self.link.subscribe("inference", lambda m: callback(m["class"], m["probs"], m["ts"]))

    def drift(self, psi, bins=None, n=None, ts=None):
        """psi = current PSI; bins = current fraction per confidence bin (4); n = inferences used."""
        self.link.publish("drift", {"psi": psi, "bins": bins, "n": n}, ts)

    def close(self):
        self.link.close()


def _demo(seconds=180):
    """Publish a PSI value every 20 s that rises then falls, crossing 0.25 and then 0.10."""
    import time

    dash = DriftMonitorDashboard()
    for i, psi in enumerate([0.03, 0.08, 0.20, 0.42, 0.55, 0.30, 0.12, 0.05, 0.04]):
        if i * 20 >= seconds:
            break
        dash.drift(psi, bins=[0.8, 0.1, 0.05, 0.05], n=100)
        print(f"PSI={psi:.3f}" + ("  [LOGIBRIDGE DRIFT ALERT]" if psi > 0.25 else ""))
        time.sleep(20)
    dash.close()


if __name__ == "__main__":
    _demo(int(sys.argv[1]) if len(sys.argv) > 1 else 180)
