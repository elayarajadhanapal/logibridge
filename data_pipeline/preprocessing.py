import os
import sys
import time
import argparse
import numpy as np
import pandas as pd
from scipy.stats import kurtosis

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from data_pipeline_dashboard_iface import PreprocessingDashboard  # noqa: E402
from dashboard.dashboard_api import DEFAULT_TRUCK_ID  # noqa: E402  (repo root added by the iface)

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
STATS_PATH = os.path.join(DATA_DIR, "training_stats.npy")

temp_buffer = []
vib_buffer = []
last_ts = [None]  # data time (Unix s) of the latest temperature reading
collected_features = []
MAX_SAMPLES = 60  # 10 minutes of data

def process_sliding_window(temp_array, vib_array):
    temp_filtered = pd.Series(temp_array).rolling(window=5, min_periods=1).mean().values
    vib_filtered = pd.Series(vib_array).rolling(window=5, min_periods=1).mean().values

    temp_mean = np.mean(temp_filtered)
    temp_std = np.std(temp_filtered)
    if len(temp_filtered) > 1:
        elapsed_seconds = len(temp_filtered) - 1
        temp_roc = ((temp_filtered[-1] - temp_filtered[0]) * 60.0 / elapsed_seconds)  # rate of change per 2 seconds
    else:
        temp_roc = 0.0
    # 30 temperature readings at 1 Hz span 29 seconds between the first and last readings. Multiplying the difference by 60 / 29 calculates the rate in °C/min.

    vib_rms = np.sqrt(np.mean(vib_filtered**2))
    vib_peak = np.max(np.abs(vib_filtered))
    vib_kurt = kurtosis(vib_filtered) if len(vib_filtered) > 3 else 0.0

    return np.array([temp_mean, temp_std, temp_roc, vib_rms, vib_peak, vib_kurt])

def load_stats(path=STATS_PATH, shift_sigma=0.0):
    """Load (mean, std) from training_stats.npy; never recomputed from live data.
    shift_sigma > 0 shifts the mean by that many std (mandatory 3-sigma experiment)."""
    if not os.path.exists(path):
        print(f"WARNING: {path} not found - publishing raw features only")
        return None
    stats = np.load(path)
    mean, std = stats[0], np.maximum(stats[1], 1e-6)
    return mean + shift_sigma * std, std

def on_temperature(value, ts):
    temp_buffer.append(value)
    last_ts[0] = ts

def on_vibration(value, ts):
    vib_buffer.append(value)

def main():
    # Set up command-line arguments
    parser = argparse.ArgumentParser(description="Edge AI Preprocessor")
    parser.add_argument("--mode", type=str, default="live",
                        help="live (default): normalise with training_stats.npy and publish features; "
                             "normal: collect 10 min and save training_stats.npy; "
                             "any other name (e.g. temp_drift): collect 10 min and save dataset_<mode>.npy")
    parser.add_argument("--stats-shift", type=float, default=0.0,
                        help="live mode: shift the stats mean by this many std (e.g. 3 for the 3-sigma experiment)")
    parser.add_argument("--truck-id", default=DEFAULT_TRUCK_ID, help=f"Truck identifier (default: {DEFAULT_TRUCK_ID})")
    args = parser.parse_args()

    stats = load_stats(shift_sigma=args.stats_shift) if args.mode == "live" else None

    dash = PreprocessingDashboard(truck_id=args.truck_id)
    dash.on_temperature(on_temperature)
    dash.on_vibration(on_vibration)

    print(f"Starting pipeline in {args.mode.upper()} mode. Waiting 30 seconds to fill the first window...")

    try:
        while True:
            time.sleep(10)
            if len(temp_buffer) >= 30 and len(vib_buffer) >= 15:
                features = process_sliding_window(temp_buffer[-30:], vib_buffer[-15:])
                norm = (features - stats[0]) / stats[1] if stats is not None else None
                ts = last_ts[0]
                dash.features(features, norm, window_start=ts - 29, ts=ts)

                np.set_printoptions(suppress=True, precision=3)
                if args.mode == "live":
                    print(f"Features: {features} | norm: {norm}")
                else:
                    collected_features.append(features)
                    print(f"Extracted Features ({len(collected_features)}/{MAX_SAMPLES}): {features}")

                if args.mode != "live" and len(collected_features) >= MAX_SAMPLES:
                    print(f"\n10 minutes of {args.mode} data collected!")
                    feature_matrix = np.array(collected_features)

                    # Logic split based on the mode provided in the command line
                    if args.mode == "normal":
                        stats_mean = np.mean(feature_matrix, axis=0)
                        stats_std = np.std(feature_matrix, axis=0)
                        training_stats = np.vstack((stats_mean, stats_std))
                        np.save(STATS_PATH, training_stats)
                        print("Saved 'training_stats.npy'")
                    else:
                        filename = f"dataset_{args.mode}.npy"
                        np.save(os.path.join(DATA_DIR, filename), feature_matrix)
                        print(f"Saved '{filename}'")

                    break

                del temp_buffer[:-20]
                del vib_buffer[:-10]
            else:
                print(f"Buffering [{args.mode.upper()}] Data... Temp: {len(temp_buffer)}/30 | Vib: {len(vib_buffer)}/15")
    except KeyboardInterrupt:
        pass
    finally:
        dash.close()

if __name__ == "__main__":
    main()
