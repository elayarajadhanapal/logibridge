"""
edge_runtime_dashboard_iface.py — MQTT interface for the two on-truck support services.

uplink_agent.py  (local alert log + store-and-forward to the operations centre):
    from edge_runtime_dashboard_iface import UplinkAgentDashboard
    dash = UplinkAgentDashboard()
    dash.on_inference(lambda cls, probs, ts: ...)      # write window record, decide alerts
    dash.on_cellular_command(lambda up: ...)           # True = signal back, False = dead zone
    dash.link_state(cellular=False)                    # on change
    dash.storage(stored_bytes, queued_bytes, sent_bytes, queued_records)   # every 1 s
    dash.alert(cls=2, msg="Critical: temp rising", raised_ts=t_raised)      # when delivered
    dash.sync(records=93, bytes_sent=4500, gap_s=5400)                      # after a flush
    dash.close()

node_monitor.py  (CPU / RAM / power of the edge node):
    from edge_runtime_dashboard_iface import NodeMonitorDashboard
    dash = NodeMonitorDashboard()
    dash.metrics(cpu_pct, power_w, ram_used_kb, ram_total_kb, power_src="estimate")   # every 1 s

Once the uplink agent is online the dashboard stops raising its own alerts and
shows only what this agent delivers. Callbacks run on the MQTT network thread.

Try it without writing any code:   python edge_runtime/edge_runtime_dashboard_iface.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root
from dashboard.dashboard_api import DEFAULT_TRUCK_ID, DashboardLink  # noqa: E402


class UplinkAgentDashboard:
    def __init__(self, truck_id=DEFAULT_TRUCK_ID, **link_options):
        self.link = DashboardLink("uplink_agent", truck_id, **link_options)

    def on_inference(self, callback):
        """callback(cls, probs, ts) for every inference result."""
        self.link.subscribe("inference", lambda m: callback(m["class"], m["probs"], m["ts"]))

    def on_cellular_command(self, callback):
        """callback(up) — the dashboard's route says the truck entered (False) or left (True) a dead zone."""
        self.link.on_control("cellular", callback)

    def link_state(self, cellular):
        """Report the link state the agent is acting on (call on change)."""
        self.link.publish("link", {"cellular": cellular})

    def storage(self, stored_bytes, queued_bytes, sent_bytes, queued_records=None):
        """Local log size, bytes waiting for signal, bytes delivered so far."""
        self.link.publish("storage", {"stored_bytes": stored_bytes, "queued_bytes": queued_bytes,
                                      "sent_bytes": sent_bytes, "queued_records": queued_records})

    def alert(self, cls, msg, raised_ts, ts=None):
        """An alert delivered to operations. cls 0 = all clear. ts = delivery time (default now)."""
        self.link.publish("alerts", {"class": cls, "msg": msg, "raised_ts": raised_ts}, ts)

    def sync(self, records, bytes_sent, gap_s=None):
        """After flushing the queue when signal returns."""
        self.link.publish("sync", {"records": records, "bytes": bytes_sent, "gap_s": gap_s})

    def close(self):
        self.link.close()


class NodeMonitorDashboard:
    def __init__(self, truck_id=DEFAULT_TRUCK_ID, **link_options):
        self.link = DashboardLink("node_monitor", truck_id, **link_options)

    def metrics(self, cpu_pct, power_w, ram_used_kb=None, ram_total_kb=None, power_src="estimate"):
        """power_src: "estimate" (laptop, E = P x t from TDP) or "measured" (USB power meter)."""
        self.link.publish("node", {"cpu_pct": cpu_pct, "power_w": power_w, "ram_used_kb": ram_used_kb,
                                   "ram_total_kb": ram_total_kb, "power_src": power_src})

    def close(self):
        self.link.close()


def _demo(seconds=60):
    """Fake store-and-forward: queue while the dashboard says no signal, flush when it returns."""
    import random
    import time

    up, node = UplinkAgentDashboard(), NodeMonitorDashboard()
    state = {"cellular": True, "queued": 0, "records": 0, "gap_start": None, "changed": True}

    def on_cellular(is_up):
        state.update(cellular=is_up, changed=True)
        print("control: cellular ->", is_up)

    up.on_cellular_command(on_cellular)
    stored = sent = 0
    for i in range(seconds):
        now = time.time()
        if state["changed"]:
            state["changed"] = False
            up.link_state(state["cellular"])
            if not state["cellular"]:
                state["gap_start"] = now
            elif state["queued"]:
                up.sync(state["records"], state["queued"], gap_s=now - (state["gap_start"] or now))
                sent += state["queued"]
                state.update(queued=0, records=0)
        if i % 10 == 9:                       # one 50-byte window record every 10 s
            stored += 50
            if state["cellular"]:
                sent += 50
            else:
                state["queued"] += 50
                state["records"] += 1
        if i == 30:
            up.alert(1, "Warning: demo alert", raised_ts=now - 2)
        up.storage(stored, state["queued"], sent, state["records"])
        node.metrics(cpu_pct=random.uniform(4, 9), power_w=3.1, ram_used_kb=640000, ram_total_kb=8388608)
        time.sleep(1)
    up.close()
    node.close()


if __name__ == "__main__":
    _demo(int(sys.argv[1]) if len(sys.argv) > 1 else 60)
