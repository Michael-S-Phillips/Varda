"""A small numpy multi-layer perceptron classifier with adjustable depth and width."""

import numpy as np

from varda.analysis.mlp import MlpClassifier


def _twoBlobs(seed=0, n=300, features=6):
    rng = np.random.default_rng(seed)
    a = rng.normal(loc=0.0, scale=0.3, size=(n, features))
    b = rng.normal(loc=1.5, scale=0.3, size=(n, features))
    X = np.vstack([a, b])
    y = np.array([0] * n + [1] * n)
    return X, y


def test_learns_to_separate_two_gaussian_blobs():
    X, y = _twoBlobs()
    model = MlpClassifier(hiddenLayers=2, neuronsPerLayer=16, seed=0)

    losses = model.fit(X, y, epochs=150, learningRate=0.01)

    assert losses[-1] < losses[0] * 0.2  # loss fell substantially
    accuracy = np.mean(model.predict(X) == y)
    assert accuracy > 0.98


def test_probabilities_are_a_distribution_over_the_classes():
    X, y = _twoBlobs()
    model = MlpClassifier(hiddenLayers=1, neuronsPerLayer=8, seed=1)
    model.fit(X, y, epochs=20)

    probabilities = model.predictProbabilities(X)

    assert probabilities.shape == (X.shape[0], 2)
    np.testing.assert_allclose(probabilities.sum(axis=1), 1.0, atol=1e-6)
    assert np.all(probabilities >= 0)


def test_architecture_follows_the_settings():
    model = MlpClassifier(hiddenLayers=3, neuronsPerLayer=5, seed=0)
    model.fit(
        np.random.default_rng(0).normal(size=(40, 4)), np.arange(40) % 3, epochs=1
    )

    assert model.layerSizes == [4, 5, 5, 5, 3]


def test_features_are_standardised_from_the_training_data():
    X = np.column_stack([np.linspace(0, 1000, 50), np.linspace(-5, 5, 50)])
    y = (X[:, 0] > 500).astype(int)
    model = MlpClassifier(hiddenLayers=1, neuronsPerLayer=4, seed=0)
    model.fit(X, y, epochs=5)

    standardised = model.standardise(X)
    np.testing.assert_allclose(standardised.mean(axis=0), 0.0, atol=1e-9)
    np.testing.assert_allclose(standardised.std(axis=0), 1.0, atol=1e-9)


def test_progress_callback_is_called_per_epoch():
    X, y = _twoBlobs(n=20)
    seen = []
    MlpClassifier(hiddenLayers=1, neuronsPerLayer=4, seed=0).fit(
        X, y, epochs=3, onEpoch=lambda epoch, loss: seen.append(epoch)
    )
    assert seen == [1, 2, 3]
