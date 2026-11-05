
import numpy as np
import tensorflow as tf

from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
)

# --------------------------------------------------
# Configuration
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

DATASET_PATH = BASE_DIR / "dataset.npz"
STATS_PATH = BASE_DIR / "training_stats.npy"
M1_MODEL_PATH = BASE_DIR / "models" / "M1" / "model.keras"
M2_MODEL_PATH = BASE_DIR / "models" / "M2" / "model.tflite"

CLASS_NAMES = ["Normal", "Warning", "Critical"]
RANDOM_STATE = 42
CALIBRATION_SAMPLES = 200


# --------------------------------------------------
# Load Dataset
# --------------------------------------------------

with np.load(DATASET_PATH) as data:
    X = data["X"].astype(np.float32)
    y = data["y"].astype(np.int32)

stats = np.load(STATS_PATH)
mean = stats[0].astype(np.float32)
std = np.maximum(stats[1], 1e-6).astype(np.float32)

# Normalize using existing training statistics
X = ((X - mean) / std).astype(np.float32)

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=RANDOM_STATE,
    stratify=y,
)

print("Dataset loaded:", X.shape)
print("Calibration samples:", CALIBRATION_SAMPLES)
print("Test samples:", len(X_test))


# --------------------------------------------------
# Load M1 FP32 Model
# --------------------------------------------------

print("\nLoading M1 FP32 model...")

model = tf.keras.models.load_model(M1_MODEL_PATH)

print("M1 model loaded:", M1_MODEL_PATH)


# --------------------------------------------------
# Representative Dataset
# --------------------------------------------------

rng = np.random.default_rng(RANDOM_STATE)

calibration_indices = rng.choice(
    len(X),
    size=CALIBRATION_SAMPLES,
    replace=False,
)

calibration_data = X[calibration_indices]


def representative_dataset():
    for sample in calibration_data:
        yield [sample.reshape(1, 6).astype(np.float32)]


# --------------------------------------------------
# Full INT8 PTQ Conversion
# --------------------------------------------------

print("\nConverting M1 to Full INT8...")

converter = tf.lite.TFLiteConverter.from_keras_model(model)

converter.optimizations = [tf.lite.Optimize.DEFAULT]
converter.representative_dataset = representative_dataset

converter.target_spec.supported_ops = [
    tf.lite.OpsSet.TFLITE_BUILTINS_INT8
]

converter.inference_input_type = tf.int8
converter.inference_output_type = tf.int8

tflite_model = converter.convert()

M2_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)

with open(M2_MODEL_PATH, "wb") as f:
    f.write(tflite_model)

print("M2 INT8 model saved:", M2_MODEL_PATH)


# --------------------------------------------------
# TFLite Inference
# --------------------------------------------------

interpreter = tf.lite.Interpreter(
    model_path=str(M2_MODEL_PATH)
)

interpreter.allocate_tensors()

input_details = interpreter.get_input_details()
output_details = interpreter.get_output_details()

input_detail = input_details[0]
output_detail = output_details[0]

input_scale, input_zero_point = input_detail["quantization"]
output_scale, output_zero_point = output_detail["quantization"]

print("\nInput dtype:", input_detail["dtype"])
print("Output dtype:", output_detail["dtype"])


def predict_int8(sample):
    sample = sample.reshape(1, 6).astype(np.float32)

    # Quantize input to INT8
    quantized_input = np.round(
        sample / input_scale + input_zero_point
    )

    quantized_input = np.clip(
        quantized_input, -128, 127
    ).astype(np.int8)

    interpreter.set_tensor(
        input_detail["index"],
        quantized_input,
    )

    interpreter.invoke()

    quantized_output = interpreter.get_tensor(
        output_detail["index"]
    )

    # Softmax output is quantized; argmax remains valid
    prediction = int(np.argmax(quantized_output[0]))

    return prediction


# --------------------------------------------------
# Evaluation
# --------------------------------------------------

print("\nEvaluating M2 INT8 model...")

y_pred = np.array([
    predict_int8(sample)
    for sample in X_test
])

accuracy = accuracy_score(y_test, y_pred)

print("\n" + "=" * 60)
print("M2 FULL INT8 CLASSIFIER EVALUATION")
print("=" * 60)

print(f"\nAccuracy: {accuracy * 100:.2f}%")

print("\nClassification Report:")
print(
    classification_report(
        y_test,
        y_pred,
        labels=[0, 1, 2],
        target_names=CLASS_NAMES,
        zero_division=0,
    )
)

print("\nConfusion Matrix:")
print(confusion_matrix(y_test, y_pred, labels=[0, 1, 2]))


# --------------------------------------------------
# Model Size
# --------------------------------------------------

model_size_kb = M2_MODEL_PATH.stat().st_size / 1024

print(f"\nM2 model size: {model_size_kb:.2f} KB")
print("M2 INT8 model saved to:", M2_MODEL_PATH)

print(f"\nM2 validation accuracy: {accuracy * 100:.2f}%")
print(f"M1 FP32 validation accuracy: 96.61%")
print(f"Accuracy difference: {(accuracy - 0.9661) * 100:+.2f}%")

print("\nM2 evaluation completed.")
