"""
inference_dashboard_iface.py — MQTT interface for inference_service.py.

    from inference_dashboard_iface import InferenceDashboard
    dash = InferenceDashboard()
    dash.on_features(lambda raw, norm, ts: ...)            # input: one window every 10 s
    dash.on_model_command(lambda model_id: ...)            # dashboard asks for M1 / M2 / M3
    dash.model_active("M2", size_kb=276, sha256="...")     # after every successful model load
    dash.inference(cls=1, probs=[0.1, 0.8, 0.1], latency_ms=0.9, model="M2", ts=window_end)
    dash.close()

The inference topic is the one the brief requires: logibridge/trucks/{truck_id}/inference.
In Docker, build from the repository root so dashboard/dashboard_api.py is copied too.

Callbacks run on the MQTT network thread: keep them short.

Try it without writing any code:   python inference/inference_dashboard_iface.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root
from dashboard.dashboard_api import DEFAULT_TRUCK_ID, DashboardLink  # noqa: E402


class InferenceDashboard:
    def __init__(self, truck_id=DEFAULT_TRUCK_ID, **link_options):
        self.link = DashboardLink("inference", truck_id, **link_options)

    def on_features(self, callback):
        """callback(raw, norm, ts) per window; norm is None if preprocessing has no stats."""
        self.link.subscribe("features", lambda m: callback(m["raw"], m.get("norm"), m["ts"]))

    def on_model_command(self, callback):
        """callback(model_id) with model_id in M1 / M2 / M3. Report the result with model_active()."""
        self.link.on_control("model", callback)

    def inference(self, cls, probs, latency_ms, model, ts=None):
        """cls 0 Normal / 1 Warning / 2 Critical; probs = 3 softmax outputs; ts = window end time."""
        self.link.publish("inference", {"class": cls, "probs": probs,
                                        "latency_ms": latency_ms, "model": model}, ts)

    def model_active(self, model, size_kb, sha256=None):
        """Call after a model file has loaded successfully (never after a failed load)."""
        self.link.publish("model_active", {"model": model, "size_kb": size_kb, "sha256": sha256})

    def close(self):
        self.link.close()


def _demo(seconds=60):
    """Turn every incoming feature window (or a timer) into a fake classification."""
    import time

    dash = InferenceDashboard()
    state = {"model": "M2", "window": None}
    dash.on_model_command(lambda m: state.update(model=m))
    dash.on_features(lambda raw, norm, ts: state.update(window=(raw, ts)))
    dash.model_active(state["model"], size_kb=276)
    shown = state["model"]
    for i in range(seconds):
        if state["model"] != shown:
            shown = state["model"]
            dash.model_active(shown, size_kb={"M1": 1104, "M2": 276, "M3": 182}[shown])
            print("control: model ->", shown)
        if i % 10 == 9:
            raw, ts = state["window"] or ([4.0, 0.3, 0.0, 0.45, 0.6, 3.0], time.time())
            cls = 2 if raw[3] > 0.9 else 1 if abs(raw[0] - 4.0) > 1 else 0
            probs = [0.05, 0.05, 0.05]
            probs[cls] = 0.90
            dash.inference(cls, probs, latency_ms=0.9, model=shown, ts=ts)
        time.sleep(1)
    dash.close()


if __name__ == "__main__":
    _demo(int(sys.argv[1]) if len(sys.argv) > 1 else 60)
