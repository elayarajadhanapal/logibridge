
import shutil
from pathlib import Path

import tensorflow as tf

BASE_DIR = Path(__file__).resolve().parent.parent

KERAS_MODEL = BASE_DIR / "data_pipeline" / "models" / "M1" / "model.keras"
ROOT_MODEL = BASE_DIR / "model.tflite"
M1_MODEL = BASE_DIR / "data_pipeline" / "models" / "M1" / "model.tflite"

print("Loading M1 FP32 Keras model...")
model = tf.keras.models.load_model(KERAS_MODEL)

print("Converting M1 to FP32 TFLite...")

converter = tf.lite.TFLiteConverter.from_keras_model(model)
tflite_model = converter.convert()

ROOT_MODEL.write_bytes(tflite_model)
M1_MODEL.write_bytes(tflite_model)

print("M1 FP32 TFLite exported successfully.")
print("Docker model:", ROOT_MODEL)
print("M1 variant:", M1_MODEL)
print(f"Model size: {ROOT_MODEL.stat().st_size / 1024:.2f} KB")
