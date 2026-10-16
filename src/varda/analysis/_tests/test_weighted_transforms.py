"""Weighted PCA, MNF and ICA: each value counts by its weight (frames used,
an inverse variance), so values with no weight (flagged, missing) neither
bend the components nor a pixel's scores; equal weights change nothing."""

import numpy as np
from varda.analysis.linear_algebra import (
    fastIca,
    inverseTransform,
    mnf,
    noiseCovariance,
    pca,
    weightedPca,
)


def _planted(n=2000, bands=12, seed=0):
    rng = np.random.default_rng(seed)
    sources = rng.normal(size=(n, 2)) * [3.0, 1.0]
    mixing = rng.normal(size=(2, bands))
    return sources @ mixing + 0.01 * rng.normal(size=(n, bands)) + 5.0


def _alignment(a, b):
    """|cos| between matching columns of two loading matrices."""
    return np.abs(np.sum(a * b, axis=0)) / (
        np.linalg.norm(a, axis=0) * np.linalg.norm(b, axis=0)
    )


def test_equal_weights_give_ordinary_pca():
    X = _planted()
    plain = pca(X, 3)
    weighted = weightedPca(X, np.full(X.shape, 7.0), 3)
    np.testing.assert_allclose(
        weighted.explainedVariance, plain.explainedVariance, rtol=1e-6
    )
    np.testing.assert_allclose(
        _alignment(weighted.loadings, plain.loadings), 1, atol=1e-6
    )
    np.testing.assert_allclose(np.abs(weighted.scores), np.abs(plain.scores), atol=1e-6)


def test_values_with_no_weight_change_nothing():
    X = _planted()
    clean = pca(X, 2)
    rng = np.random.default_rng(1)
    bad = rng.random(X.shape) < 0.05  # flagged: wild values
    corrupted = np.where(bad, 1e4 * rng.normal(size=X.shape), X)
    corrupted[3, 4] = np.nan  # and a missing one
    weights = np.where(bad, 0.0, 1.0)
    weighted = weightedPca(corrupted, weights, 2)
    assert _alignment(weighted.loadings, clean.loadings).min() > 0.999
    assert (
        _alignment(pca(np.nan_to_num(corrupted), 2).loadings, clean.loadings).min()
        < 0.9
    )
    # each pixel's scores are fitted to its weighted values only: pixels with
    # flagged values rebuild as well as the rest (to the sampling error of a
    # mean from 95% of the values), where ordinary PCA is thrown far off
    rebuilt = inverseTransform(weighted.scores, weighted.inverse, weighted.mean, 2)
    error = np.abs(rebuilt - X)[~bad]
    assert np.median(error) < 0.02 and error.max() < 0.3
    plain = pca(np.nan_to_num(corrupted), 2)
    plainError = np.abs(
        inverseTransform(plain.scores, plain.inverse, plain.mean, 2) - X
    )
    assert np.median(plainError[~bad]) > 10 * np.median(error)


def _scene(rows=40, cols=50, bands=10, seed=0):
    """Smooth independent sources (scene structure) mixed into bands, plus
    white noise: what MNF and ICA are for."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:rows, 0:cols]
    sources = np.stack(
        [
            np.sign(np.sin(xx / 4.0)),  # square waves: non-Gaussian
            np.sin(yy / 5.0) ** 3,
            ((xx + yy) % 13) / 13.0 - 0.5,
        ],
        axis=2,
    ).reshape(-1, 3)
    mixing = rng.normal(size=(3, bands))
    data = sources @ mixing + 0.05 * rng.normal(size=(rows * cols, bands)) + 2.0
    return data.reshape(rows, cols, bands), sources


def _smoothScene(rows=60, cols=70, bands=10, seed=0):
    """Smooth scene structure under white noise: what MNF's neighbor
    differences take to be noise holds."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:rows, 0:cols]
    sources = np.stack(
        [np.tanh(3 * np.sin(xx / 6.0)), np.sin(yy / 7.0) ** 3, np.cos((xx + yy) / 9.0)],
        axis=2,
    ).reshape(-1, 3)
    data = sources @ rng.normal(size=(3, bands)) + 0.05 * rng.normal(
        size=(rows * cols, bands)
    )
    return (data + 2.0).reshape(rows, cols, bands)


def _corrupt(cube, share=0.05, seed=3):
    rng = np.random.default_rng(seed)
    bad = rng.random(cube.shape) < share
    return np.where(bad, 1e4 * rng.normal(size=cube.shape), cube), np.where(
        bad, 0.0, 1.0
    )


def test_mnf_with_equal_weights_is_ordinary_mnf():
    cube, _ = _scene()
    valid = np.ones(cube.shape[:2], bool)
    X = cube.reshape(-1, cube.shape[2])
    plain = mnf(X, noiseCovariance(cube, valid), 3)
    ones = np.ones(cube.shape)
    weighted = mnf(
        X, noiseCovariance(cube, valid, weights=ones), 3, weights=ones.reshape(X.shape)
    )
    np.testing.assert_allclose(
        _alignment(weighted.loadings, plain.loadings), 1, atol=1e-6
    )
    np.testing.assert_allclose(
        weighted.explainedVariance, plain.explainedVariance, rtol=1e-3
    )


def test_mnf_ignores_values_with_no_weight():
    cube = _smoothScene()
    valid = np.ones(cube.shape[:2], bool)
    X = cube.reshape(-1, cube.shape[2])
    clean = mnf(X, noiseCovariance(cube, valid), 3)
    corrupted, weights = _corrupt(cube)
    weighted = mnf(
        corrupted.reshape(X.shape),
        noiseCovariance(corrupted, valid, weights=weights),
        3,
        weights=weights.reshape(X.shape),
    )
    # the leading (signal) components; the last is at the noise floor
    assert _alignment(weighted.loadings[:, :2], clean.loadings[:, :2]).min() > 0.99


def _bestMatch(a, b):
    """For each column of a, the best |correlation| with a column of b."""
    k = a.shape[1]
    c = np.abs(np.corrcoef(a.T, b.T)[:k, k:])
    return c.max(axis=1)


def test_ica_with_equal_weights_is_ordinary_ica():
    cube, _ = _scene()
    X = cube.reshape(-1, cube.shape[2])
    plain = fastIca(X, 3)
    weighted = fastIca(X, 3, weights=np.ones(X.shape))
    assert _bestMatch(weighted.scores, plain.scores).min() > 0.999


def test_ica_finds_the_sources_despite_values_with_no_weight():
    cube, sources = _scene()
    corrupted, weights = _corrupt(cube)
    X = corrupted.reshape(-1, cube.shape[2])
    weighted = fastIca(X, 3, weights=weights.reshape(X.shape))
    assert _bestMatch(weighted.scores, sources).min() > 0.95
    rebuilt = weighted.scores @ weighted.inverse + weighted.mean
    good = weights.reshape(X.shape) > 0
    assert np.median(np.abs(rebuilt - cube.reshape(X.shape))[good]) < 0.1


def test_a_weighted_noise_covariance_is_kept_positive():
    from varda.analysis.linear_algebra import shrunkToPositive

    bad = np.array([[1.0, 0.99, -0.99], [0.99, 1.0, 0.99], [-0.99, 0.99, 1.0]])
    assert np.linalg.eigvalsh(bad)[0] < 0  # pairwise estimates can do this
    fixed = shrunkToPositive(bad)
    assert np.linalg.eigvalsh(fixed)[0] >= 1e-3 * 0.999
    np.testing.assert_allclose(np.diag(fixed), np.diag(bad))  # variances kept
