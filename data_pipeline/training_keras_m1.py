
import argparse
from pathlib import Path

import numpy as np
import tensorflow as tf

from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
)
from sklearn.model_selection import train_test_split


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

DATA_DIR = Path(__file__).resolve().parent

DEFAULT_DATASET_PATH = DATA_DIR / "dataset.npz"
DEFAULT_STATS_PATH = DATA_DIR / "training_stats.npy"
DEFAULT_MODEL_PATH = DATA_DIR / "models" / "M1" / "model.keras"

CLASS_NAMES = ["Normal", "Warning", "Critical"]

RANDOM_STATE = 42


# ---------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------

def set_seed():
    np.random.seed(RANDOM_STATE)
    tf.keras.utils.set_random_seed(RANDOM_STATE)


# ---------------------------------------------------------
# Dataset Loading
# ---------------------------------------------------------

def load_dataset(dataset_path: Path):
    if not dataset_path.exists():
        raise FileNotFoundError(
            f"Dataset not found: {dataset_path}"
        )

    dataset = np.load(dataset_path)

    X = dataset["X"].astype(np.float32)
    y = dataset["y"].astype(np.int32)

    if X.ndim != 2 or X.shape[1] != 6:
        raise ValueError(f"Expected X shape (n, 6), got {X.shape}")

    if len(X) != len(y):
        raise ValueError("Features and labels have different lengths.")

    if not np.isfinite(X).all():
        raise ValueError("Dataset contains NaN or infinite values.")

    if not np.isin(y, [0, 1, 2]).all():
        raise ValueError("Labels must be 0, 1, or 2.")

    print(f"Dataset loaded: {dataset_path}")
    print(f"Features shape: {X.shape}")
    print(f"Labels shape: {y.shape}")
    print("Class distribution:", np.unique(y, return_counts=True))

    return X, y


# ---------------------------------------------------------
# Normalization
# ---------------------------------------------------------

def load_training_stats(stats_path: Path):
    if not stats_path.exists():
        raise FileNotFoundError(
            f"Training statistics not found: {stats_path}"
        )

    stats = np.load(stats_path)

    if stats.shape != (2, 6):
        raise ValueError(
            f"Expected training_stats shape (2, 6), got {stats.shape}"
        )

    mean = stats[0].astype(np.float32)
    std = np.maximum(stats[1], 1e-6).astype(np.float32)

    print(f"Training statistics loaded: {stats_path}")

    return mean, std


def normalize_features(X, mean, std):
    return ((X - mean) / std).astype(np.float32)


# ---------------------------------------------------------
# M1 Architecture
# ---------------------------------------------------------

def build_model():
    model = tf.keras.Sequential(
        [
            tf.keras.Input(shape=(6,), name="features"),

            tf.keras.layers.Dense(
                32,
                activation="relu",
                name="hidden_1",
            ),

            tf.keras.layers.Dense(
                16,
                activation="relu",
                name="hidden_2",
            ),

            tf.keras.layers.Dense(
                3,
                activation="softmax",
                name="class_probabilities",
            ),
        ],
        name="logibridge_m1",
    )

    model.compile(
        optimizer=tf.keras.optimizers.Adam(),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )

    return model


# ---------------------------------------------------------
# Evaluation
# ---------------------------------------------------------

def evaluate_model(model, X_test, y_test):

    probabilities = model.predict(
        X_test,
        verbose=0,
    )

    predictions = np.argmax(
        probabilities,
        axis=1,
    )

    accuracy = accuracy_score(
        y_test,
        predictions,
    )

    print("\n" + "=" * 60)
    print("M1 FP32 CLASSIFIER EVALUATION")
    print("=" * 60)

    print(f"\nAccuracy: {accuracy * 100:.2f}%")

    print("\nClassification Report:")

    print(
        classification_report(
            y_test,
            predictions,
            labels=[0, 1, 2],
            target_names=CLASS_NAMES,
            zero_division=0,
        )
    )

    print("Confusion Matrix:")

    print(
        confusion_matrix(
            y_test,
            predictions,
            labels=[0, 1, 2],
        )
    )

    return accuracy


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

def main():

    parser = argparse.ArgumentParser(
        description="Train LogiBridge M1 FP32 model"
    )

    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET_PATH,
    )

    parser.add_argument(
        "--stats",
        type=Path,
        default=DEFAULT_STATS_PATH,
    )

    parser.add_argument(
        "--model",
        type=Path,
        default=DEFAULT_MODEL_PATH,
    )

    args = parser.parse_args()

    set_seed()

    # Load dataset
    X, y = load_dataset(args.dataset)

    # Load clean-data normalization statistics
    mean, std = load_training_stats(args.stats)

    # Normalize features
    X = normalize_features(X, mean, std)

    # Stratified train/validation split
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.20,
        random_state=RANDOM_STATE,
        stratify=y,
    )

    print("\nTraining samples:", len(X_train))
    print("Validation samples:", len(X_test))

    # Build M1
    model = build_model()

    model.summary()

    # Train
    print("\nTraining M1 FP32 model...")

    model.fit(
        X_train,
        y_train,
        validation_data=(X_test, y_test),
        epochs=100,
        batch_size=32,
        callbacks=[
            tf.keras.callbacks.EarlyStopping(
                monitor="val_loss",
                patience=30,
                restore_best_weights=True,
            )
        ],
        verbose=1,
    )

    # Evaluate
    accuracy = evaluate_model(
        model,
        X_test,
        y_test,
    )

    # Save model
    args.model.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    model.save(args.model)

    print(f"\nM1 FP32 model saved to: {args.model}")
    print(f"M1 validation accuracy: {accuracy * 100:.2f}%")

    if accuracy >= 0.88:
        print("Accuracy requirement (>=88%) achieved.")
    else:
        print("Accuracy requirement (>=88%) not achieved.")


if __name__ == "__main__":
    main()
