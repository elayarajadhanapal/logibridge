import time
import json
import argparse
import numpy as np
import pandas as pd
from scipy.stats import kurtosis
import paho.mqtt.client as mqtt

# Set up command-line arguments
parser = argparse.ArgumentParser(description="Edge AI Preprocessor")
parser.add_argument("--mode", type=str, default="normal", help="Data collection mode (e.g., normal, temp_drift)")
args = parser.parse_args()

temp_buffer = []
vib_buffer = []
collected_features = []
MAX_SAMPLES = 60  # 10 minutes of data

def process_sliding_window(temp_array, vib_array):
    temp_filtered = pd.Series(temp_array).rolling(window=5, min_periods=1).mean().values
    vib_filtered = pd.Series(vib_array).rolling(window=5, min_periods=1).mean().values
    
    temp_mean = np.mean(temp_filtered)
    temp_std = np.std(temp_filtered)
    temp_roc = (temp_filtered[-1] - temp_filtered[0]) * 2
    
    vib_rms = np.sqrt(np.mean(vib_filtered**2))
    vib_peak = np.max(np.abs(vib_filtered))
    vib_kurt = kurtosis(vib_filtered) if len(vib_filtered) > 3 else 0.0
    
    return np.array([temp_mean, temp_std, temp_roc, vib_rms, vib_peak, vib_kurt])

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        val = None
        if "value" in payload: val = payload["value"]
        elif "temperature" in payload and "temperature" in msg.topic: val = payload["temperature"]
        elif "vibration" in payload and "vibration" in msg.topic: val = payload["vibration"]
        else:
            for k, v in payload.items():
                if isinstance(v, (int, float)):
                    val = v
                    break
        if val is not None:
            if "temperature" in msg.topic: temp_buffer.append(val)
            elif "vibration" in msg.topic: vib_buffer.append(val)
            
            print(f"\rBuffering [{args.mode.upper()}] Data... Temp: {len(temp_buffer)}/30 | Vib: {len(vib_buffer)}/15", end="")
    except Exception:
        pass

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
client.on_message = on_message
client.connect("localhost", 1883, 60)
client.subscribe("logibridge/sensors/#")
client.loop_start()

print(f"Starting pipeline in {args.mode.upper()} mode. Waiting 30 seconds to fill the first window...")

try:
    while True:
        time.sleep(10)
        if len(temp_buffer) >= 30 and len(vib_buffer) >= 15:
            features = process_sliding_window(temp_buffer[-30:], vib_buffer[-15:])
            collected_features.append(features)
            
            np.set_printoptions(suppress=True, precision=3)
            print(f"\nExtracted Features ({len(collected_features)}/{MAX_SAMPLES}): {features}")
            
            if len(collected_features) >= MAX_SAMPLES:
                print(f"\n10 minutes of {args.mode} data collected!")
                feature_matrix = np.array(collected_features)
                
                # Logic split based on the mode provided in the command line
                if args.mode == "normal":
                    stats_mean = np.mean(feature_matrix, axis=0)
                    stats_std = np.std(feature_matrix, axis=0)
                    training_stats = np.vstack((stats_mean, stats_std))
                    np.save("training_stats.npy", training_stats)
                    np.save("dataset_normal.npy", feature_matrix)
                    print("Saved 'training_stats.npy' AND 'dataset_normal.npy'")
                else:
                    filename = f"dataset_{args.mode}.npy"
                    np.save(filename, feature_matrix)
                    print(f"Saved '{filename}'")
                    
                break
            
            del temp_buffer[:-20]
            del vib_buffer[:-10]
except KeyboardInterrupt:
    pass
finally:
    client.loop_stop()
    client.disconnect()