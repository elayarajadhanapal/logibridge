
from pathlib import Path

import numpy as np
import tensorflow as tf

BASE_DIR = Path(__file__).resolve().parent.parent

keras_path = BASE_DIR / "data_pipeline/models/M1/model.keras"
tflite_path = BASE_DIR / "data_pipeline/models/M1/model.tflite"
dataset_path = BASE_DIR / "data_pipeline/dataset.npz"
stats_path = BASE_DIR / "data_pipeline/training_stats.npy"

with np.load(dataset_path) as data:
    X = data["X"].astype(np.float32)
    y = data["y"].astype(np.int32)

stats = np.load(stats_path)
mean = stats[0].astype(np.float32)
std = np.maximum(stats[1], 1e-6).astype(np.float32)
X = ((X - mean) / std).astype(np.float32)

keras_model = tf.keras.models.load_model(keras_path)
keras_predictions = keras_model.predict(X, verbose=0)

interpreter = tf.lite.Interpreter(model_path=str(tflite_path))
interpreter.allocate_tensors()

input_detail = interpreter.get_input_details()[0]
output_detail = interpreter.get_output_details()[0]

tflite_predictions = []

for sample in X:
    interpreter.set_tensor(
        input_detail["index"],
        sample.reshape(1, 6),
    )
    interpreter.invoke()

    prediction = interpreter.get_tensor(
        output_detail["index"]
    )[0]

    tflite_predictions.append(prediction)

tflite_predictions = np.asarray(tflite_predictions)

keras_classes = np.argmax(keras_predictions, axis=1)
tflite_classes = np.argmax(tflite_predictions, axis=1)

print("Keras accuracy:", np.mean(keras_classes == y))
print("TFLite accuracy:", np.mean(tflite_classes == y))
print("Prediction agreement:", np.mean(keras_classes == tflite_classes))
print(
    "Maximum probability difference:",
    np.max(np.abs(keras_predictions - tflite_predictions)),
)
