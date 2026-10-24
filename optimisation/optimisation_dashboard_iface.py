"""
optimisation_dashboard_iface.py — sends benchmark results for M1 / M2 / M3 to the dashboard.

At the end of benchmark.py:
    from optimisation_dashboard_iface import publish_benchmark_csv
    publish_benchmark_csv("optimisation/results/benchmark_results.csv")

or, from rows you already have in memory:
    from optimisation_dashboard_iface import publish_benchmark_rows
    publish_benchmark_rows([{"variant": "M2", "mean_latency_ms": 0.8, "size_kb": 276, ...}])

CSV columns: variant, mean_latency_ms, p95_latency_ms, size_kb, accuracy, energy_mj, class2_recall
(accuracy and class2_recall in percent). The message is retained, so a dashboard
opened later still shows the numbers. No broker? Paste the CSV into the dashboard's
Connect tab instead.

Try it without writing any code:   python optimisation/optimisation_dashboard_iface.py
"""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # repo root
from dashboard.dashboard_api import DEFAULT_TRUCK_ID, DashboardLink  # noqa: E402

# benchmark_results.csv column -> dashboard metric name
CSV_TO_DASHBOARD = {
    "mean_latency_ms": "latencyMs",
    "p95_latency_ms": "p95Ms",
    "size_kb": "sizeKB",
    "accuracy": "accuracy",
    "energy_mj": "energyMJ",
    "class2_recall": "recallC2",
}


def publish_benchmark_rows(rows, truck_id=DEFAULT_TRUCK_ID, **link_options):
    """rows: list of dicts keyed by the CSV column names, one per variant."""
    models = {}
    for row in rows:
        variant = str(row["variant"]).strip()
        models[variant] = {dash_key: float(row[col]) for col, dash_key in CSV_TO_DASHBOARD.items()
                           if row.get(col) not in (None, "")}
    link = DashboardLink("benchmark", truck_id, announce=False, **link_options)
    link.publish("models", models)
    link.close()
    return models


def publish_benchmark_csv(path, truck_id=DEFAULT_TRUCK_ID, **link_options):
    with open(path, newline="") as f:
        return publish_benchmark_rows(list(csv.DictReader(f)), truck_id, **link_options)


if __name__ == "__main__":
    sample = [
        {"variant": "M1", "mean_latency_ms": 2.1, "p95_latency_ms": 2.9, "size_kb": 1104,
         "accuracy": 94.2, "energy_mj": 0.31, "class2_recall": 96.0},
        {"variant": "M2", "mean_latency_ms": 0.8, "p95_latency_ms": 1.1, "size_kb": 276,
         "accuracy": 93.4, "energy_mj": 0.12, "class2_recall": 97.1},
        {"variant": "M3", "mean_latency_ms": 0.6, "p95_latency_ms": 0.9, "size_kb": 182,
         "accuracy": 92.1, "energy_mj": 0.09, "class2_recall": 95.4},
    ]
    print("published (sample numbers, not results):", publish_benchmark_rows(sample))
