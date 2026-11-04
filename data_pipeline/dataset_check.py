import numpy as np

data = np.load("data_pipeline/training_stats.npy")

X = data["X"]
y = data["y"]

print("Features:", X.shape)
print("Labels:", y.shape)

print("Class distribution:")
print("Normal:", np.sum(y == 0))
print("Warning:", np.sum(y == 1))
print("Critical:", np.sum(y == 2))