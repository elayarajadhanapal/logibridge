
import time
from pathlib import Path

import numpy as np
import psutil
import tensorflow as tf

from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score


# --------------------------------------------------
# Configuration
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

DATASET_PATH = BASE_DIR / "dataset.npz"
STATS_PATH = BASE_DIR / "training_stats.npy"

MODEL_PATHS = {
    "M1_FP32": BASE_DIR / "models" / "M1" / "model.keras",
    "M2_INT8": BASE_DIR / "models" / "M2" / "model.tflite",
    "M3_INT8": BASE_DIR / "models" / "M3" / "model.tflite",
}

WARMUP_RUNS = 10
BENCHMARK_RUNS = 200
RANDOM_STATE = 42

# Replace with your processor's estimated CPU package TDP.
# 15 W is an initial assumption, not a measured power value.
CPU_TDP_W = 15.0


# --------------------------------------------------
# Load Dataset and Normalize
# --------------------------------------------------

data = np.load(DATASET_PATH)
with np.load(DATASET_PATH) as data:
    X = data["X"].astype(np.float32)
    y = data["y"].astype(np.int32)

stats = np.load(STATS_PATH)
mean = stats[0].astype(np.float32)
std = np.maximum(stats[1], 1e-6).astype(np.float32)

X = ((X - mean) / std).astype(np.float32)

_, X_test, _, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=RANDOM_STATE,
    stratify=y,
)

print("Validation samples:", len(X_test))
print("Warm-up runs:", WARMUP_RUNS)
print("Benchmark runs:", BENCHMARK_RUNS)
print("CPU TDP estimate:", CPU_TDP_W, "W")


# --------------------------------------------------
# M1 FP32 Predictor
# --------------------------------------------------

def load_m1():
    model = tf.keras.models.load_model(MODEL_PATHS["M1_FP32"])

    def predict(sample):
        output = model(
            sample.reshape(1, 6),
            training=False,
        ).numpy()

        return int(np.argmax(output[0]))

    return predict


# --------------------------------------------------
# TFLite Predictor
# --------------------------------------------------

def load_tflite(model_path):
    interpreter = tf.lite.Interpreter(
        model_path=str(model_path)
    )
    interpreter.allocate_tensors()

    input_detail = interpreter.get_input_details()[0]
    output_detail = interpreter.get_output_details()[0]

    input_scale, input_zero_point = input_detail["quantization"]

    if input_detail["dtype"] == np.int8 and input_scale == 0:
        raise ValueError("Invalid INT8 input quantization scale.")

    def predict(sample):
        sample = sample.reshape(1, 6).astype(np.float32)

        if input_detail["dtype"] == np.int8:
            input_data = np.round(
                sample / input_scale + input_zero_point
            )
            input_data = np.clip(
                input_data, -128, 127
            ).astype(np.int8)
        else:
            input_data = sample.astype(input_detail["dtype"])

        interpreter.set_tensor(
            input_detail["index"],
            input_data,
        )

        interpreter.invoke()

        output = interpreter.get_tensor(
            output_detail["index"]
        )

        return int(np.argmax(output[0]))

    return predict


# --------------------------------------------------
# Benchmark Function
# --------------------------------------------------


def measure_energy(predict):
    process = psutil.Process()
    cpu_count = psutil.cpu_count(logical=True) or 1

    # Start CPU utilization measurement
    process.cpu_percent(interval=None)

    count = 0
    start = time.perf_counter()

    # Run a sustained workload so CPU utilization can be measured
    while time.perf_counter() - start < 2.0:
        predict(X_test[count % len(X_test)])
        count += 1

    elapsed = time.perf_counter() - start
    cpu_percent = process.cpu_percent(interval=None)

    utilization_fraction = min(
        max(cpu_percent / (cpu_count * 100), 0.0),
        1.0,
    )

    estimated_power_w = CPU_TDP_W * utilization_fraction

    energy_per_inference_mj = (
        estimated_power_w * elapsed / count * 1000
    )

    return cpu_percent, energy_per_inference_mj


def benchmark_model(name, predict, model_path):

    print(f"\nBenchmarking {name}...")

    # Warm-up
    for i in range(WARMUP_RUNS):
        predict(X_test[i % len(X_test)])

    # Measure individual inference latency
    latencies_ms = []

    process = psutil.Process()
    process.cpu_percent(interval=None)

    start_time = time.perf_counter()

    for i in range(BENCHMARK_RUNS):
        sample = X_test[i % len(X_test)]

        inference_start = time.perf_counter()
        predict(sample)
        inference_end = time.perf_counter()

        latencies_ms.append(
            (inference_end - inference_start) * 1000
        )

    elapsed_seconds = time.perf_counter() - start_time

    
    cpu_count = psutil.cpu_count(logical=True) or 1

    cpu_percent, energy_per_inference_mj = measure_energy(predict)
    # Approximate fraction of total logical CPU capacity used
    cpu_utilization = cpu_percent / (
        (psutil.cpu_count(logical=True) or 1) * 100
    )

   # estimated_power_w = CPU_TDP_W * cpu_utilization

    # # E = P * t; convert joules to millijoules
    # energy_per_inference_mj = (
    #     estimated_power_w
    #     * elapsed_seconds
    #     / BENCHMARK_RUNS
    #     * 1000
    # )

    # Validation accuracy
    predictions = np.array([
        predict(sample) for sample in X_test
    ])

    accuracy = accuracy_score(y_test, predictions) * 100

    mean_latency = float(np.mean(latencies_ms))
    p95_latency = float(np.percentile(latencies_ms, 95))

    model_size_kb = model_path.stat().st_size / 1024

    result = {
        "model": name,
        "mean_latency_ms": mean_latency,
        "p95_latency_ms": p95_latency,
        "model_size_kb": model_size_kb,
        "accuracy_percent": accuracy,
        "cpu_utilization_percent": cpu_utilization * 100,
        "estimated_energy_mj": energy_per_inference_mj,
    }

    print(f"Mean latency: {mean_latency:.4f} ms")
    print(f"P95 latency: {p95_latency:.4f} ms")
    print(f"Model size: {model_size_kb:.2f} KB")
    print(f"Accuracy: {accuracy:.2f}%")
    print(f"CPU utilization: {cpu_utilization * 100:.2f}%")
    print(f"Estimated energy: {energy_per_inference_mj:.6f} mJ")

    return result


# --------------------------------------------------
# Run All Benchmarks
# --------------------------------------------------

results = []

for name, model_path in MODEL_PATHS.items():

    if not model_path.exists():
        raise FileNotFoundError(
            f"Model not found: {model_path}"
        )

    if name == "M1_FP32":
        predictor = load_m1()
    else:
        predictor = load_tflite(model_path)

    result = benchmark_model(
        name,
        predictor,
        model_path,
    )

    results.append(result)


# --------------------------------------------------
# Final Comparison
# --------------------------------------------------

print("\n" + "=" * 90)
print("F2 MODEL PERFORMANCE COMPARISON")
print("=" * 90)

print(
    f"{'Model':<12}"
    f"{'Mean(ms)':>12}"
    f"{'P95(ms)':>12}"
    f"{'Size(KB)':>12}"
    f"{'Accuracy':>12}"
    f"{'Energy(mJ)':>14}"
)

for result in results:
    print(
        f"{result['model']:<12}"
        f"{result['mean_latency_ms']:>12.4f}"
        f"{result['p95_latency_ms']:>12.4f}"
        f"{result['model_size_kb']:>12.2f}"
        f"{result['accuracy_percent']:>11.2f}%"
        f"{result['estimated_energy_mj']:>14.6f}"
    )

print("\nF2 benchmarking completed.")
