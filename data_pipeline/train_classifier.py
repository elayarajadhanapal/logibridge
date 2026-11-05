
import argparse
from pathlib import Path

import joblib
import numpy as np

from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
)
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPClassifier


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

DATA_DIR = Path(__file__).resolve().parent

DEFAULT_DATASET_PATH = DATA_DIR / "dataset.npz"
DEFAULT_STATS_PATH = DATA_DIR / "training_stats.npy"
DEFAULT_MODEL_PATH = DATA_DIR / "classifier.joblib"

CLASS_NAMES = ["Normal", "Warning", "Critical"]


# ---------------------------------------------------------
# Dataset Loading
# ---------------------------------------------------------

def load_dataset(dataset_path: Path):
    """Load dataset features and labels."""

    if not dataset_path.exists():
        raise FileNotFoundError(
            f"Dataset not found: {dataset_path}"
        )

    dataset = np.load(dataset_path)

    X = dataset["X"]
    y = dataset["y"]

    if X.ndim != 2 or X.shape[1] != 6:
        raise ValueError(
            f"Expected X shape (n_samples, 6), got {X.shape}"
        )

    if len(X) != len(y):
        raise ValueError(
            "Features and labels have different lengths."
        )

    if not np.isfinite(X).all():
        raise ValueError(
            "Dataset contains NaN or infinite feature values."
        )

    if not np.isin(y, [0, 1, 2]).all():
        raise ValueError(
            "Labels must contain only classes 0, 1, and 2."
        )

    print(f"Dataset loaded: {dataset_path}")
    print(f"Features shape: {X.shape}")
    print(f"Labels shape: {y.shape}")
    print("Class distribution:", np.unique(y, return_counts=True))

    return X, y


# ---------------------------------------------------------
# Feature Normalization
# ---------------------------------------------------------

def load_training_stats(stats_path: Path):
    """Load normalization statistics generated from clean data."""

    if not stats_path.exists():
        raise FileNotFoundError(
            f"Training statistics not found: {stats_path}"
        )

    stats = np.load(stats_path)

    if stats.shape != (2, 6):
        raise ValueError(
            f"Expected training_stats shape (2, 6), "
            f"got {stats.shape}"
        )

    mean = stats[0]
    std = np.maximum(stats[1], 1e-6)

    print(f"Training statistics loaded: {stats_path}")

    return mean, std


def normalize_features(X, mean, std):
    """Normalize features using saved clean-data statistics."""

    return (X - mean) / std


# ---------------------------------------------------------
# Classifier Training
# ---------------------------------------------------------

def train_classifier(X_train, y_train):
    """Train the MLP classifier."""

    model = MLPClassifier(
        hidden_layer_sizes=(32, 16),
        activation="relu",
        solver="adam",
        max_iter=1000,
        early_stopping=True,
        random_state=42,
    )

    print("\nTraining MLP classifier...")

    model.fit(X_train, y_train)

    return model


# ---------------------------------------------------------
# Evaluation
# ---------------------------------------------------------

def evaluate_classifier(model, X_test, y_test):
    """Evaluate the trained classifier."""

    predictions = model.predict(X_test)

    accuracy = accuracy_score(y_test, predictions)

    print("\n" + "=" * 60)
    print("CLASSIFIER EVALUATION")
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
        description="Train LogiBridge anomaly classifier"
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

    # Load dataset
    X, y = load_dataset(args.dataset)

    # Load clean-data normalization statistics
    mean, std = load_training_stats(args.stats)

    # Normalize features
    X = normalize_features(X, mean, std)

    # Split dataset: 80% training, 20% validation
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.20,
        random_state=42,
        stratify=y,
    )

    print("\nTraining samples:", len(X_train))
    print("Validation samples:", len(X_test))

    # Train model
    model = train_classifier(X_train, y_train)

    # Evaluate model
    accuracy = evaluate_classifier(
        model,
        X_test,
        y_test,
    )

    # Save trained model
    args.model.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    joblib.dump(model, args.model)

    print(f"\nModel saved to: {args.model}")

    if accuracy >= 0.88:
        print("Accuracy requirement (>88%) achieved.")
    else:
        print("Accuracy requirement (>88%) not achieved.")


if __name__ == "__main__":
    main()
