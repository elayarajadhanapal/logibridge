
import numpy as np
import tensorflow as tf
import keras
import tensorflow_model_optimization as tfmot

from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

# --------------------------------------------------
# Configuration
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

DATASET_PATH = BASE_DIR / "dataset.npz"
STATS_PATH = BASE_DIR / "training_stats.npy"
M1_PATH = BASE_DIR / "models" / "M1" / "model.keras"
M3_PATH = BASE_DIR / "models" / "M3" / "model.tflite"

CLASS_NAMES = ["Normal", "Warning", "Critical"]
RANDOM_STATE = 42
CALIBRATION_SAMPLES = 200
PRUNING_TARGET = 0.35


# --------------------------------------------------
# Load Dataset
# --------------------------------------------------

np.random.seed(RANDOM_STATE)
tf.random.set_seed(RANDOM_STATE)


with np.load(DATASET_PATH) as data:
    X = data["X"].astype(np.float32)
    y = data["y"].astype(np.int32)


stats = np.load(STATS_PATH)
mean = stats[0].astype(np.float32)
std = np.maximum(stats[1], 1e-6).astype(np.float32)

X = ((X - mean) / std).astype(np.float32)

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.20,
    random_state=RANDOM_STATE,
    stratify=y,
)

print("Dataset:", X.shape)
print("Training samples:", len(X_train))
print("Validation samples:", len(X_test))


# --------------------------------------------------
# Load M1 Baseline
# --------------------------------------------------

keras3_model = keras.models.load_model(M1_PATH, compile=False)
base_model = tf.keras.Sequential([
    tf.keras.layers.Input(shape=(6,), name="features"),
    tf.keras.layers.Dense(32, activation="relu", name="hidden_1"),
    tf.keras.layers.Dense(16, activation="relu", name="hidden_2"),
    tf.keras.layers.Dense(3, activation="softmax", name="class_probabilities"),
], name="logibridge_m1")
base_model.set_weights(keras3_model.get_weights())

print("\nM1 model loaded.")


# --------------------------------------------------
# Phase 1: PolynomialDecay Weight Pruning
# --------------------------------------------------

print("\nApplying PolynomialDecay pruning...")

steps_per_epoch = int(np.ceil(len(X_train) / 32))

pruning_schedule = tfmot.sparsity.keras.PolynomialDecay(
    initial_sparsity=0.0,
    final_sparsity=PRUNING_TARGET,
    begin_step=0,
    end_step=steps_per_epoch * 20,
)

pruned_model = tfmot.sparsity.keras.prune_low_magnitude(
    base_model,
    pruning_schedule=pruning_schedule,
)

pruned_model.compile(
    optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
    loss="sparse_categorical_crossentropy",
    metrics=["accuracy"],
)

pruned_model.fit(
    X_train,
    y_train,
    validation_data=(X_test, y_test),
    epochs=20,
    batch_size=32,
    callbacks=[
        tfmot.sparsity.keras.UpdatePruningStep(),
    ],
    verbose=1,
)

# Remove pruning wrappers and masks
stripped_model = tfmot.sparsity.keras.strip_pruning(pruned_model)

print("\nPolynomialDecay pruning completed.")


# --------------------------------------------------
# Phase 2: Physical Structured Neuron Pruning
# --------------------------------------------------

print("\nReducing hidden neurons by 35%...")

weights = stripped_model.get_weights()

W1, b1 = weights[0], weights[1]
W2, b2 = weights[2], weights[3]
W3, b3 = weights[4], weights[5]

# Retain 65% of neurons in each hidden layer
keep_h1 = int(np.ceil(W1.shape[1] * 0.65))
keep_h2 = int(np.ceil(W2.shape[1] * 0.65))

# Rank second hidden neurons by output contribution
importance_h2 = np.linalg.norm(W3, axis=1)
idx_h2 = np.argsort(importance_h2)[-keep_h2:]

# Rank first hidden neurons by contribution to retained layer 2
importance_h1 = np.linalg.norm(
    W2[:, idx_h2],
    axis=1,
)
idx_h1 = np.argsort(importance_h1)[-keep_h1:]

# Build physically smaller network
structured_model = tf.keras.Sequential([
    tf.keras.layers.Input(shape=(6,), name="features"),
    tf.keras.layers.Dense(keep_h1, activation="relu"),
    tf.keras.layers.Dense(keep_h2, activation="relu"),
    tf.keras.layers.Dense(3, activation="softmax"),
])

structured_model.compile(
    optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
    loss="sparse_categorical_crossentropy",
    metrics=["accuracy"],
)

# Transfer selected neurons and corresponding connections
structured_model.layers[0].set_weights([
    W1[:, idx_h1],
    b1[idx_h1],
])

structured_model.layers[1].set_weights([
    W2[np.ix_(idx_h1, idx_h2)],
    b2[idx_h2],
])

structured_model.layers[2].set_weights([
    W3[idx_h2, :],
    b3,
])

print("Original hidden layers:", W1.shape[1], W2.shape[1])
print("Structured hidden layers:", keep_h1, keep_h2)


# --------------------------------------------------
# Phase 3: Fine-tune Structured Model
# --------------------------------------------------

print("\nFine-tuning structured model...")

structured_model.fit(
    X_train,
    y_train,
    validation_data=(X_test, y_test),
    epochs=100,
    batch_size=32,
    callbacks=[
        tf.keras.callbacks.EarlyStopping(
            monitor="val_loss",
            patience=15,
            restore_best_weights=True,
        ),
    ],
    verbose=1,
)


# --------------------------------------------------
# Phase 4: Full INT8 PTQ
# --------------------------------------------------

print("\nPreparing INT8 calibration...")

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


converter = tf.lite.TFLiteConverter.from_keras_model(
    structured_model
)

converter.optimizations = [tf.lite.Optimize.DEFAULT]
converter.representative_dataset = representative_dataset

converter.target_spec.supported_ops = [
    tf.lite.OpsSet.TFLITE_BUILTINS_INT8
]

converter.inference_input_type = tf.int8
converter.inference_output_type = tf.int8

tflite_model = converter.convert()

M3_PATH.parent.mkdir(parents=True, exist_ok=True)

with open(M3_PATH, "wb") as f:
    f.write(tflite_model)

print("M3 INT8 model saved:", M3_PATH)


# --------------------------------------------------
# Phase 5: TFLite Evaluation
# --------------------------------------------------

interpreter = tf.lite.Interpreter(model_path=str(M3_PATH))
interpreter.allocate_tensors()

input_detail = interpreter.get_input_details()[0]
output_detail = interpreter.get_output_details()[0]

input_scale, input_zero_point = input_detail["quantization"]
output_scale, output_zero_point = output_detail["quantization"]

print("\nInput dtype:", input_detail["dtype"])
print("Output dtype:", output_detail["dtype"])


def predict_int8(sample):
    sample = sample.reshape(1, 6).astype(np.float32)

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

    output = interpreter.get_tensor(
        output_detail["index"]
    )

    return int(np.argmax(output[0]))


print("\nEvaluating M3...")

y_pred = np.array([
    predict_int8(sample)
    for sample in X_test
])

accuracy = accuracy_score(y_test, y_pred)

print("\n" + "=" * 60)
print("M3 STRUCTURED PRUNED INT8 EVALUATION")
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

model_size_kb = M3_PATH.stat().st_size / 1024

print(f"\nM3 model size: {model_size_kb:.2f} KB")
print(f"M1 FP32 accuracy: 96.61%")
print(f"M2 INT8 accuracy: 96.61%")
print(f"M3 INT8 accuracy: {accuracy * 100:.2f}%")

print("\nM3 evaluation completed.")
