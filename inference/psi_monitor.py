
import argparse
import json
import os
import time
from collections import deque
from pathlib import Path
from queue import Queue, Empty

import numpy as np
import paho.mqtt.client as mqtt

BROKER_HOST = os.getenv("LOGIBRIDGE_MQTT_HOST", "localhost")
BROKER_PORT = int(os.getenv("LOGIBRIDGE_MQTT_PORT", "1883"))
TRUCK_ID = os.getenv("TRUCK_ID", "MH15-RF-0427")

TOPIC = f"logibridge/trucks/{TRUCK_ID}/inference"
REFERENCE_PATH = Path("data_pipeline/reference_dist.json")

BIN_EDGES = [0.0, 0.25, 0.50, 0.75, 1.0000001]
EPSILON = 1e-6

messages = Queue()


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print(f"Connected to MQTT: {BROKER_HOST}:{BROKER_PORT}")
        client.subscribe(TOPIC)
        print(f"Subscribed: {TOPIC}")
    else:
        print(f"MQTT connection failed: {reason_code}")


def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        probs = payload["probs"]
        confidence = float(max(probs))
        messages.put(confidence)
    except (KeyError, ValueError, TypeError, json.JSONDecodeError):
        print("Invalid inference message received")


def create_client():
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(BROKER_HOST, BROKER_PORT)
    client.loop_start()
    return client


def build_reference(count):
    client = create_client()
    confidences = []

    print(f"Collecting {count} clean Normal inference confidences...")
    print("Keep simulator running with --anomaly none.")

    try:
        while len(confidences) < count:
            try:
                confidence = messages.get(timeout=2)
                confidences.append(confidence)
                print(f"\rCollected: {len(confidences)}/{count}", end="")
            except Empty:
                pass
    finally:
        client.loop_stop()
        client.disconnect()

    counts, _ = np.histogram(confidences, bins=BIN_EDGES)
    proportions = counts / counts.sum()

    reference = {
        "truck_id": TRUCK_ID,
        "sample_count": len(confidences),
        "bin_edges": BIN_EDGES,
        "bin_counts": counts.tolist(),
        "bin_proportions": proportions.tolist(),
        "created_at": time.time(),
    }

    REFERENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    REFERENCE_PATH.write_text(json.dumps(reference, indent=2))

    print(f"\nReference distribution saved: {REFERENCE_PATH}")
    print("Bin proportions:", proportions.tolist())


def calculate_psi(reference, current):
    ref = np.asarray(reference, dtype=float)
    cur = np.asarray(current, dtype=float)

    ref = (ref + EPSILON) / (ref + EPSILON).sum()
    cur = (cur + EPSILON) / (cur + EPSILON).sum()

    return float(np.sum((cur - ref) * np.log(cur / ref)))


def monitor():
    reference = json.loads(REFERENCE_PATH.read_text())
    reference_dist = reference["bin_proportions"]

    rolling = deque(maxlen=100)
    client = create_client()
    last_check = time.time()

    print("PSI monitoring started.")
    print("Rolling window: 100 | Interval: 60 seconds")

    try:
        while True:
            try:
                confidence = messages.get(timeout=1)
                rolling.append(confidence)
            except Empty:
                pass

            if time.time() - last_check >= 60:
                last_check = time.time()

                if len(rolling) < 100:
                    print(f"Waiting for 100 predictions: {len(rolling)}/100")
                    continue

                counts, _ = np.histogram(rolling, bins=BIN_EDGES)
                current_dist = counts / counts.sum()
                psi = calculate_psi(reference_dist, current_dist)

                print(f"[PSI] {psi:.3f}")

                if psi > 0.25:
                    print(f"[LOGIBRIDGE DRIFT ALERT] PSI={psi:.3f}")
                elif psi < 0.10:
                    print(f"[LOGIBRIDGE RECOVERY] PSI={psi:.3f}")

    except KeyboardInterrupt:
        print("PSI monitoring stopped.")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=["reference", "monitor"],
        required=True,
    )
    parser.add_argument("--count", type=int, default=300)
    args = parser.parse_args()

    if args.mode == "reference":
        build_reference(args.count)
    else:
        monitor()
