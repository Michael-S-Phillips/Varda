"""PCA, MNF and FastICA on synthetic cubes with known structure."""

import numpy as np
import pytest

from varda.analysis.linear_algebra import (
    fastIca,
    flattenValid,
    noiseCovariance,
    pca,
    mnf,
    unflatten,
)


def _plantedCube(seed=0, rows=30, cols=40, bands=12, latent=3, noise=0.01):
    """Bands are linear mixes of ``latent`` random sources plus a little noise."""
    rng = np.random.default_rng(seed)
    sources = rng.normal(size=(rows * cols, latent)) * np.array([3.0, 2.0, 1.0])
    mixing = rng.normal(size=(latent, bands))
    data = sources @ mixing + noise * rng.normal(size=(rows * cols, bands))
    return data.reshape(rows, cols, bands), sources


def test_flatten_valid_drops_nodata_and_nan_pixels_and_unflatten_restores_them():
    cube = np.ones((3, 4, 2))
    cube[0, 0, :] = -999.0  # nodata pixel
    cube[1, 1, 0] = np.nan  # partly invalid pixel
    X, valid = flattenValid(cube, nodata=-999.0)

    assert valid.sum() == 10 and X.shape == (10, 2)
    restored = unflatten(X, valid)
    assert restored.shape == (3, 4, 2)
    assert np.isnan(restored[0, 0]).all() and np.isnan(restored[1, 1]).all()
    np.testing.assert_array_equal(restored[2, 3], [1.0, 1.0])


def test_pca_explains_the_planted_variance_in_decreasing_order():
    cube, _sources = _plantedCube()
    X, _valid = flattenValid(cube, nodata=None)

    result = pca(X, components=5)

    assert result.scores.shape == (X.shape[0], 5)
    assert result.loadings.shape == (X.shape[1], 5)
    assert np.all(np.diff(result.explainedVariance) <= 0)
    assert result.explainedVariance[:3].sum() > 0.99  # three latent sources
    # scores are uncorrelated
    corr = np.corrcoef(result.scores[:, :3].T)
    np.testing.assert_allclose(corr, np.eye(3), atol=0.02)


def test_noise_covariance_is_estimated_from_neighbour_differences():
    rng = np.random.default_rng(1)
    flat = np.full((20, 20, 3), 5.0)  # perfectly smooth scene ...
    noisy = flat + rng.normal(scale=[0.1, 1.0, 0.01], size=flat.shape)  # ... plus noise
    cov = noiseCovariance(noisy, np.ones((20, 20), dtype=bool))

    assert cov.shape == (3, 3)
    # noise variances recovered in the right order (band 2 noisiest, band 3 quietest)
    variances = np.diag(cov)
    assert variances[1] > variances[0] > variances[2]
    np.testing.assert_allclose(variances, [0.01, 1.0, 0.0001], rtol=0.4)


def test_mnf_puts_high_snr_structure_first_even_when_a_noisy_band_dominates_variance():
    rng = np.random.default_rng(2)
    n = 4000
    signal = np.sin(np.linspace(0, 20, n))  # smooth, low-variance signal
    cube = np.zeros((40, 100, 3))
    cube[:, :, 0] = signal.reshape(40, 100)
    cube[:, :, 1] = signal.reshape(40, 100)
    cube[:, :, 2] = rng.normal(scale=5.0, size=(40, 100))  # pure high-variance noise
    valid = np.ones((40, 100), dtype=bool)
    X, _ = flattenValid(cube, nodata=None)
    cov = noiseCovariance(cube, valid)

    result = mnf(X, cov, components=3)

    # the first MNF component follows the smooth signal, not the noisy band
    first = result.scores[:, 0]
    assert abs(np.corrcoef(first, signal)[0, 1]) > 0.95
    assert np.all(np.diff(result.explainedVariance) <= 0)  # SNR ordering


def test_fastica_recovers_independent_non_gaussian_sources():
    rng = np.random.default_rng(3)
    n = 5000
    sources = np.column_stack([rng.uniform(-1, 1, n), np.sign(rng.normal(size=n))])
    mixing = np.array([[1.0, 0.5], [0.3, 1.0]])
    X = sources @ mixing

    recovered = fastIca(X, components=2, maxIterations=400, seed=0).scores

    corr = np.abs(np.corrcoef(recovered.T, sources.T)[:2, 2:])
    # each recovered component matches exactly one source (up to sign/permutation)
    assert np.allclose(np.sort(corr.max(axis=1)), [1.0, 1.0], atol=0.05)
    assert np.allclose(corr.max(axis=0), [1.0, 1.0], atol=0.05)


def test_pca_requires_at_least_as_many_samples_as_components():
    with pytest.raises(ValueError):
        pca(np.zeros((2, 5)), components=5)
