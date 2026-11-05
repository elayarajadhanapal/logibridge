
import hashlib
import os
import queue
import time
from pathlib import Path

import numpy as np
import tensorflow as tf

from inference_dashboard_iface import InferenceDashboard


# --------------------------------------------------
# Configuration
# --------------------------------------------------

MODEL_PATH = Path(os.getenv("MODEL_PATH", "/app/model.tflite"))
MODEL_DIR = Path(os.getenv("MODEL_DIR", "/app/models"))
STATS_PATH = Path(
    os.getenv("TRAINING_STATS_PATH", "/app/training_stats.npy")
)

TRUCK_ID = os.getenv("TRUCK_ID", "truck-001")
MODEL_NAME = os.getenv("MODEL_NAME", "M1")

CLASS_NAMES = ["Normal", "Warning", "Critical"]

MODEL_VARIANTS = {
    "M1": MODEL_DIR / "M1" / "model.tflite",
    "M2": MODEL_DIR / "M2" / "model.tflite",
    "M3": MODEL_DIR / "M3" / "model.tflite",
}

EVENT_QUEUE = queue.Queue()


# --------------------------------------------------
# Feature Normalization
# --------------------------------------------------

stats = np.load(STATS_PATH)

FEATURE_MEAN = stats[0].astype(np.float32)
FEATURE_STD = np.maximum(
    stats[1].astype(np.float32),
    1e-6,
)


def prepare_features(raw, norm):
    """
    Use normalized features supplied by the upstream pipeline.
    Otherwise normalize raw features with training statistics.
    """

    if norm is not None:
        features = np.asarray(norm, dtype=np.float32)
    else:
        raw = np.asarray(raw, dtype=np.float32)
        features = (raw - FEATURE_MEAN) / FEATURE_STD

    if features.shape != (6,):
        raise ValueError(
            f"Expected 6 features, received shape {features.shape}"
        )

    if not np.all(np.isfinite(features)):
        raise ValueError("Features contain invalid values.")

    return features.reshape(1, 6)


# --------------------------------------------------
# Model Loading
# --------------------------------------------------

def load_model(model_path):
    model_path = Path(model_path)

    if not model_path.is_file():
        raise FileNotFoundError(
            f"Model file not found: {model_path}"
        )

    model_bytes = model_path.read_bytes()
    sha256 = hashlib.sha256(model_bytes).hexdigest()

    interpreter = tf.lite.Interpreter(
        model_path=str(model_path)
    )
    interpreter.allocate_tensors()

    input_detail = interpreter.get_input_details()[0]
    output_detail = interpreter.get_output_details()[0]

    if tuple(input_detail["shape"]) != (1, 6):
        raise ValueError(
            f"Unexpected model input shape: {input_detail['shape']}"
        )

    print(f"Loaded model: {model_path}")
    print(f"Input dtype: {input_detail['dtype']}")
    print(f"Output dtype: {output_detail['dtype']}")

    return {
        "interpreter": interpreter,
        "input": input_detail,
        "output": output_detail,
        "path": model_path,
        "sha256": sha256,
    }


# --------------------------------------------------
# Inference
# --------------------------------------------------

def predict(model, features):
    interpreter = model["interpreter"]
    input_detail = model["input"]
    output_detail = model["output"]

    input_scale, input_zero_point = input_detail["quantization"]

    if input_detail["dtype"] == np.int8:
        if input_scale == 0:
            raise ValueError("Invalid INT8 input quantization scale.")

        input_data = np.round(
            features / input_scale + input_zero_point
        )

        input_data = np.clip(
            input_data, -128, 127
        ).astype(np.int8)

    else:
        input_data = features.astype(input_detail["dtype"])

    interpreter.set_tensor(
        input_detail["index"],
        input_data,
    )

    start = time.perf_counter()

    interpreter.invoke()

    latency_ms = (
        time.perf_counter() - start
    ) * 1000

    output = interpreter.get_tensor(
        output_detail["index"]
    )[0]

    if output_detail["dtype"] == np.int8:
        output_scale, output_zero_point = (
            output_detail["quantization"]
        )

        output = (
            output.astype(np.float32) - output_zero_point
        ) * output_scale

    probabilities = output.astype(np.float32)

    if not np.all(np.isfinite(probabilities)):
        raise ValueError("Model produced invalid probabilities.")

    total = float(np.sum(probabilities))

    if total <= 0:
        raise ValueError("Invalid model probability output.")

    probabilities = probabilities / total

    predicted_class = int(np.argmax(probabilities))

    return (
        predicted_class,
        probabilities.tolist(),
        latency_ms,
    )


# --------------------------------------------------
# Service
# --------------------------------------------------

def main():
    global MODEL_NAME

    print("Starting LogiBridge inference service...")
    print("Truck ID:", TRUCK_ID)
    print("Initial model:", MODEL_NAME)
    print("MODEL_PATH:", MODEL_PATH)

    active_path = MODEL_PATH

    active_model = load_model(active_path)

    dashboard = InferenceDashboard(truck_id=TRUCK_ID)

    model_size_kb = active_path.stat().st_size / 1024

    dashboard.model_active(
        MODEL_NAME,
        size_kb=model_size_kb,
        sha256=active_model["sha256"],
    )

    # MQTT callbacks only enqueue events.
    # Inference and model loading happen on the main thread.

    dashboard.on_features(
        lambda raw, norm, ts: EVENT_QUEUE.put(
            ("features", raw, norm, ts)
        )
    )

    dashboard.on_model_command(
        lambda model_id: EVENT_QUEUE.put(
            ("model", model_id)
        )
    )

    print("Inference service ready.")

    try:
        while True:
            event = EVENT_QUEUE.get()

            if event[0] == "model":
                requested_model = event[1]

                if requested_model not in MODEL_VARIANTS:
                    print("Unknown model command:", requested_model)
                    continue

                requested_path = MODEL_VARIANTS[requested_model]

                try:
                    new_model = load_model(requested_path)

                    # Switch only after successful loading.
                    active_model = new_model
                    active_path = requested_path
                    MODEL_NAME = requested_model

                    dashboard.model_active(
                        MODEL_NAME,
                        size_kb=active_path.stat().st_size / 1024,
                        sha256=active_model["sha256"],
                    )

                    print("Active model changed to:", MODEL_NAME)

                except Exception as exc:
                    print(
                        f"Model switch failed for {requested_model}: {exc}"
                    )

            elif event[0] == "features":
                _, raw, norm, ts = event

                try:
                    features = prepare_features(raw, norm)

                    cls, probs, latency_ms = predict(
                        active_model,
                        features,
                    )

                    dashboard.inference(
                        cls=cls,
                        probs=probs,
                        latency_ms=latency_ms,
                        model=MODEL_NAME,
                        ts=ts,
                    )

                    print(
                        f"Truck={TRUCK_ID} "
                        f"Model={MODEL_NAME} "
                        f"Class={CLASS_NAMES[cls]} "
                        f"Confidence={max(probs):.3f} "
                        f"Latency={latency_ms:.3f} ms"
                    )

                except Exception as exc:
                    print("Inference error:", exc)

    except KeyboardInterrupt:
        print("Stopping inference service...")

    finally:
        dashboard.close()


if __name__ == "__main__":
    main()
