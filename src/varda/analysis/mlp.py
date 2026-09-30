"""A small multi-layer perceptron classifier in plain numpy.

Adjustable depth and width, tanh hidden units, softmax output trained with
cross-entropy and Adam on shuffled mini-batches. Features are standardised
from the training data. Sized for spectra (hundreds of features, up to a
few hundred thousand samples), not for images of pixels.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np


class MlpClassifier:
    def __init__(self, hiddenLayers: int = 2, neuronsPerLayer: int = 32, seed: int = 0):
        self.hiddenLayers = max(1, int(hiddenLayers))
        self.neuronsPerLayer = max(1, int(neuronsPerLayer))
        self._rng = np.random.default_rng(seed)
        self.layerSizes: list[int] = []
        self._weights: list[np.ndarray] = []
        self._biases: list[np.ndarray] = []
        self._mean = np.zeros(0)
        self._std = np.ones(0)

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        epochs: int = 200,
        learningRate: float = 0.01,
        batchSize: int = 256,
        onEpoch: Callable[[int, float], None] | None = None,
    ) -> list[float]:
        """Train on integer labels ``y`` (0..k-1); returns the per-epoch mean loss."""
        X = np.asarray(X, dtype=np.float64)
        y = np.asarray(y, dtype=np.int64)
        classes = int(y.max()) + 1
        self._mean = X.mean(axis=0)
        self._std = np.where(X.std(axis=0) > 0, X.std(axis=0), 1.0)
        Z = self.standardise(X)
        self._initialise(Z.shape[1], classes)

        adam = _Adam(self._weights + self._biases, learningRate)
        losses = []
        for epoch in range(1, epochs + 1):
            order = self._rng.permutation(Z.shape[0])
            epochLoss = 0.0
            for start in range(0, Z.shape[0], batchSize):
                batch = order[start : start + batchSize]
                loss, gradients = self._lossAndGradients(Z[batch], y[batch])
                adam.step(self._weights + self._biases, gradients)
                epochLoss += loss * batch.size
            losses.append(epochLoss / Z.shape[0])
            if onEpoch is not None:
                onEpoch(epoch, losses[-1])
        return losses

    def predictProbabilities(self, X: np.ndarray) -> np.ndarray:
        activations, _ = self._forward(
            self.standardise(np.asarray(X, dtype=np.float64))
        )
        return activations[-1]

    def predict(self, X: np.ndarray) -> np.ndarray:
        return np.argmax(self.predictProbabilities(X), axis=1)

    def standardise(self, X: np.ndarray) -> np.ndarray:
        return (X - self._mean) / self._std

    # --- internals ---

    def _initialise(self, features: int, classes: int) -> None:
        self.layerSizes = [
            features,
            *([self.neuronsPerLayer] * self.hiddenLayers),
            classes,
        ]
        self._weights, self._biases = [], []
        for fanIn, fanOut in zip(self.layerSizes[:-1], self.layerSizes[1:]):
            limit = np.sqrt(6.0 / (fanIn + fanOut))  # Xavier/Glorot uniform
            self._weights.append(self._rng.uniform(-limit, limit, size=(fanIn, fanOut)))
            self._biases.append(np.zeros(fanOut))

    def _forward(self, Z: np.ndarray) -> tuple[list[np.ndarray], list[np.ndarray]]:
        activations, preActivations = [Z], []
        for i, (W, b) in enumerate(zip(self._weights, self._biases)):
            pre = activations[-1] @ W + b
            preActivations.append(pre)
            if i < len(self._weights) - 1:
                activations.append(np.tanh(pre))
            else:
                activations.append(_softmax(pre))
        return activations, preActivations

    def _lossAndGradients(
        self, Z: np.ndarray, y: np.ndarray
    ) -> tuple[float, list[np.ndarray]]:
        activations, _ = self._forward(Z)
        probabilities = activations[-1]
        n = Z.shape[0]
        loss = float(-np.mean(np.log(probabilities[np.arange(n), y] + 1e-12)))

        # backpropagation: softmax + cross-entropy gives (p - onehot) at the output
        delta = probabilities.copy()
        delta[np.arange(n), y] -= 1.0
        delta /= n
        weightGradients: list[np.ndarray] = []
        biasGradients: list[np.ndarray] = []
        for i in reversed(range(len(self._weights))):
            weightGradients.insert(0, activations[i].T @ delta)
            biasGradients.insert(0, delta.sum(axis=0))
            if i > 0:
                delta = (delta @ self._weights[i].T) * (1.0 - activations[i] ** 2)
        return loss, weightGradients + biasGradients


class _Adam:
    def __init__(self, parameters: list[np.ndarray], learningRate: float):
        self.learningRate = learningRate
        self.beta1, self.beta2, self.epsilon = 0.9, 0.999, 1e-8
        self.m = [np.zeros_like(p) for p in parameters]
        self.v = [np.zeros_like(p) for p in parameters]
        self.t = 0

    def step(self, parameters: list[np.ndarray], gradients: list[np.ndarray]) -> None:
        self.t += 1
        for i, (p, g) in enumerate(zip(parameters, gradients)):
            self.m[i] = self.beta1 * self.m[i] + (1 - self.beta1) * g
            self.v[i] = self.beta2 * self.v[i] + (1 - self.beta2) * g * g
            mHat = self.m[i] / (1 - self.beta1**self.t)
            vHat = self.v[i] / (1 - self.beta2**self.t)
            p -= self.learningRate * mHat / (np.sqrt(vHat) + self.epsilon)


def _softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - logits.max(axis=1, keepdims=True)
    exp = np.exp(shifted)
    return exp / exp.sum(axis=1, keepdims=True)
