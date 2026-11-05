import argparse
import json
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

import numpy as np
import paho.mqtt.client as mqtt


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_PIPELINE_DIR = Path(__file__).resolve().parent

SIMULATOR_SCRIPT = DATA_PIPELINE_DIR / "simulator.py"
PREPROCESSING_SCRIPT = DATA_PIPELINE_DIR / "preprocessing.py"

FEATURES_TOPIC = "logibridge/trucks/{truck_id}/features"

FEATURE_NAMES = [
    "temp_mean",
    "temp_std",
    "temp_roc",
    "vib_rms",
    "vib_peak",
    "vib_kurtosis",
]

SCENARIOS = [
   {
        "mode": "none",
        "label": 0,
        "duration": 1200,
        "name": "Normal",
    },
    {
        "mode": "temp_drift",
        "label": 1,
        "duration": 900,
        "name": "Warning",
    },
    {
        "mode": "combined",
        "label": 2,
        "duration": 900,
        "name": "Critical",
    },
]

STARTUP_DELAY_SECONDS = 3
FINAL_WINDOW_WAIT_SECONDS = 12


# ---------------------------------------------------------
# Dataset Collector
# ---------------------------------------------------------

class DatasetCollector:

    def __init__(self, truck_id):

        self.truck_id = truck_id

        self.features_topic = FEATURES_TOPIC.format(
            truck_id=truck_id
        )

        self.client = mqtt.Client(
            client_id=f"logiedge-dataset-{truck_id}"
        )

        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        self.connected = threading.Event()

        self.current_label = None

        self.samples = []
        self.labels = []

        self.seen_windows = set()

        self.lock = threading.Lock()

    # -----------------------------------------------------

    def on_connect(self, client, userdata, flags, rc):

        if rc != 0:
            print(f"MQTT connection failed: {rc}")
            return

        print("Dataset collector connected to MQTT.")

        client.subscribe(self.features_topic)

        self.connected.set()

    # -----------------------------------------------------

    def on_message(self, client, userdata, message):

        if message.topic != self.features_topic:
            return

        try:
            payload = json.loads(
                message.payload.decode("utf-8")
            )

            raw_features = payload.get("raw")
            window_start = payload.get("window_start")

            if raw_features is None or window_start is None:
                return

            if len(raw_features) != len(FEATURE_NAMES):
                return

            features = np.asarray(
                raw_features,
                dtype=np.float64,
            )

            if not np.all(np.isfinite(features)):
                return

            label = self.current_label

            if label is None:
                return

            window_key = (
                label,
                float(window_start),
            )

            with self.lock:

                if window_key in self.seen_windows:
                    return

                self.seen_windows.add(window_key)

                self.samples.append(features)
                self.labels.append(label)

                count = sum(
                    current_label == label
                    for current_label in self.labels
                )

                total = len(self.labels)

            print(
                f"[DATASET] "
                f"Class={label} | "
                f"Samples={count} | "
                f"Total={total}"
            )

        except (ValueError, TypeError, KeyError) as exc:

            print(
                f"[DATASET] Ignoring invalid message: {exc}"
            )

    # -----------------------------------------------------

    def connect(self, host="localhost", port=1883):

        self.client.connect(
            host,
            port,
            keepalive=10,
        )

        self.client.loop_start()

        if not self.connected.wait(timeout=10):

            raise TimeoutError(
                "Dataset collector MQTT connection failed."
            )

    # -----------------------------------------------------

    def set_label(self, label):

        self.current_label = label

    # -----------------------------------------------------

    def get_sample_count(self, label):

        with self.lock:

            return sum(
                current_label == label
                for current_label in self.labels
            )

    # -----------------------------------------------------

    def print_progress(self):

        with self.lock:

            labels = np.asarray(
                self.labels,
                dtype=np.int64,
            )

        print("\n========== DATASET PROGRESS ==========")

        for label, name in [
            (0, "Normal"),
            (1, "Warning"),
            (2, "Critical"),
        ]:

            count = int(
                np.sum(labels == label)
            )

            print(
                f"{name:<10}: {count:>4} samples"
            )

        print(f"Total      : {len(labels):>4} samples")

        print("====================================\n")

    # -----------------------------------------------------

    def close(self):

        self.client.loop_stop()
        self.client.disconnect()


# ---------------------------------------------------------
# Process Management
# ---------------------------------------------------------

def start_preprocessing():

    command = [
        sys.executable,
        str(PREPROCESSING_SCRIPT),
        "--mode",
        "live",
    ]

    print("\nStarting preprocessing...")

    process = subprocess.Popen(
        command,
        cwd=PROJECT_ROOT,
        creationflags=(
            subprocess.CREATE_NEW_PROCESS_GROUP
            if os.name == "nt"
            else 0
        ),
    )

    time.sleep(STARTUP_DELAY_SECONDS)

    if process.poll() is not None:

        raise RuntimeError(
            "Preprocessing exited during startup."
        )

    print("Preprocessing process started.")

    return process


# ---------------------------------------------------------

def stop_process(process, name):

    if process is None:
        return

    if process.poll() is not None:
        return

    print(f"\nStopping {name}...")

    try:

        if os.name == "nt":
            process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            process.send_signal(signal.SIGINT)

        process.wait(timeout=10)

    except subprocess.TimeoutExpired:

        print(f"{name} did not stop gracefully.")

        process.kill()
        process.wait()

    except OSError as exc:

        print(
            f"Could not stop {name} gracefully: {exc}"
        )

        process.terminate()
        process.wait(timeout=10)

    print(f"{name} stopped.")


# ---------------------------------------------------------

def run_simulator(truck_id, anomaly, duration):

    command = [
        sys.executable,
        str(SIMULATOR_SCRIPT),
        "--truck-id",
        truck_id,
        "--anomaly",
        anomaly,
        "--duration",
        str(duration),
    ]

    print("\nStarting simulator:")
    print(" ".join(command))

    process = subprocess.Popen(
        command,
        cwd=PROJECT_ROOT,
        creationflags=(
            subprocess.CREATE_NEW_PROCESS_GROUP
            if os.name == "nt"
            else 0
        ),
    )

    return process


# ---------------------------------------------------------
# Scenario Execution
# ---------------------------------------------------------

def collect_scenario(collector, scenario, truck_id):

    mode = scenario["mode"]
    label = scenario["label"]
    name = scenario["name"]
    duration = scenario["duration"]

    print("\n" + "=" * 55)
    print(f"SCENARIO: {name}")
    print(f"Mode    : {mode}")
    print(f"Label   : {label}")
    print(f"Duration: {duration} seconds")
    print("=" * 55)

    preprocessing_process = None
    simulator_process = None

    collector.set_label(None)

    try:

        # Start preprocessing with fresh buffers.
        preprocessing_process = start_preprocessing()

        # Start collecting samples for this class.
        collector.set_label(label)

        # Start simulator.
        simulator_process = run_simulator(
            truck_id=truck_id,
            anomaly=mode,
            duration=duration,
        )

        return_code = simulator_process.wait()

        if return_code != 0:

            raise RuntimeError(
                f"Simulator failed for {name}. "
                f"Exit code: {return_code}"
            )

        print(
            f"\nSimulator completed successfully: {name}"
        )

        # Allow preprocessing to emit its final feature window.
        print(
            f"Waiting {FINAL_WINDOW_WAIT_SECONDS} seconds "
            "for final feature processing..."
        )

        time.sleep(FINAL_WINDOW_WAIT_SECONDS)

    finally:

        collector.set_label(None)

        stop_process(
            simulator_process,
            "Simulator",
        )

        stop_process(
            preprocessing_process,
            "Preprocessing",
        )

    actual_samples = collector.get_sample_count(label)

    print(f"\nCompleted scenario: {name}")
    print(f"Collected samples: {actual_samples}")

    collector.print_progress()


# ---------------------------------------------------------
# Dataset Saving
# ---------------------------------------------------------

def save_dataset(collector, output_path):

    with collector.lock:

        if not collector.samples:

            raise RuntimeError(
                "No feature samples collected."
            )

        X = np.vstack(collector.samples)

        y = np.asarray(
            collector.labels,
            dtype=np.int64,
        )

    output_path = Path(output_path)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    np.savez_compressed(
        output_path,
        X=X,
        y=y,
        feature_names=np.asarray(
            FEATURE_NAMES,
        ),
    )

    print("\n" + "=" * 55)
    print("DATASET GENERATION COMPLETED")
    print("=" * 55)

    print(f"Output file : {output_path}")
    print(f"Feature shape: {X.shape}")
    print(f"Label shape  : {y.shape}")

    for label, name in [
        (0, "Normal"),
        (1, "Warning"),
        (2, "Critical"),
    ]:

        count = int(
            np.sum(y == label)
        )

        print(
            f"{name:<10}: {count} samples"
        )

    print(f"Total samples: {len(y)}")


# ---------------------------------------------------------
# CLI
# ---------------------------------------------------------

def parse_arguments():

    parser = argparse.ArgumentParser(
        description="Generate labelled LogiEdge dataset."
    )

    parser.add_argument(
        "--truck-id",
        default="MH15-RF-0427",
    )

    parser.add_argument(
        "--output",
        default=str(
            DATA_PIPELINE_DIR / "dataset.npz"
        ),
    )

    parser.add_argument(
        "--mqtt-host",
        default="localhost",
    )

    parser.add_argument(
        "--mqtt-port",
        type=int,
        default=1883,
    )

    return parser.parse_args()


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

def main():

    args = parse_arguments()

    collector = DatasetCollector(
        args.truck_id,
    )

    try:

        collector.connect(
            host=args.mqtt_host,
            port=args.mqtt_port,
        )

        for scenario in SCENARIOS:

            collect_scenario(
                collector=collector,
                scenario=scenario,
                truck_id=args.truck_id,
            )

        save_dataset(
            collector=collector,
            output_path=args.output,
        )

    except KeyboardInterrupt:

        print("\nDataset generation interrupted.")

    except Exception as exc:

        print(f"\nDataset generation failed: {exc}")

        raise

    finally:

        collector.close()

        print("Dataset collector disconnected.")


if __name__ == "__main__":
    main()