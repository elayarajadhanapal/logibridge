from pathlib import Path

import numpy as np

dataset_path = Path(__file__).resolve().with_name("dataset.npz")

with np.load(dataset_path) as data:
    X = data["X"]
    y = data["y"]

print("Features:", X.shape)
print("Labels:", y.shape)
print("Classes:", np.unique(y, return_counts=True))
print("NaN:", np.isnan(X).any())
print("Inf:", np.isinf(X).any())
