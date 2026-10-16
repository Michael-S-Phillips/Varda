"""Weighted PCA: each value counts by its weight (a sample count, an inverse
variance), so values with no weight (flagged, missing) neither bend the
components nor a pixel's scores."""

import numpy as np
from affine import Affine
from pyproj import CRS

from varda.analysis.analysis import AnalysisContext
from varda.analysis.linear_algebra import inverseTransform, pca, weightedPca
from varda.analysis.registry import ANALYSES
from varda.analysis.transforms import WeightedPcaAnalysis, WeightKind
from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource


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


def _products(shape=(20, 25, 8)):
    rows, cols, bands = shape
    X = _planted(rows * cols, bands).reshape(shape)
    counts = np.random.default_rng(2).integers(0, 11, shape).astype(np.float32)
    transform = Affine(100, 0, 0, 0, -100, 0)
    crs = CRS.from_user_input("+proj=eqc +R=1560800 +units=m +no_defs")
    cube = VardaRaster(
        ArrayDataSource(X.astype(np.float32), transform=transform, crs=crs), name="AGG"
    )
    count = VardaRaster(
        ArrayDataSource(counts, transform=transform, crs=crs), name="COUNT"
    )
    perPixel = VardaRaster(
        ArrayDataSource(counts[:, :, :1], transform=transform, crs=crs), name="ONE"
    )
    other = VardaRaster(
        ArrayDataSource(counts[:5], transform=transform, crs=crs), name="SMALL"
    )
    return cube, count, perPixel, other


def test_the_analysis_weights_by_an_image_on_the_same_grid():
    assert WeightedPcaAnalysis in ANALYSES
    cube, count, perPixel, other = _products()
    analysis = WeightedPcaAnalysis()
    analysis.setContext(AnalysisContext(images=[cube, count, perPixel, other]))
    analysis.prepareFor(cube)
    assert analysis.unavailableReason(cube) == ""
    assert [i.name for i in analysis.weights.imageProvider()] == ["COUNT", "ONE"]
    analysis.weights.set(count)
    result = analysis.run(cube, lambda *_: None)
    assert result.bandNames[0].startswith("WPC 1 (")
    assert "transform" in result.extraMetadata
    analysis.weights.set(perPixel)  # one band: a weight per pixel
    analysis.weightKind.set(WeightKind.INVERSE_VARIANCE)
    assert analysis.run(cube, lambda *_: None).bandCount == 8


def test_without_a_weights_image_it_says_what_to_open():
    cube, *_ = _products()
    analysis = WeightedPcaAnalysis()
    analysis.setContext(AnalysisContext(images=[cube]))
    analysis.prepareFor(cube)
    assert "weights" in analysis.unavailableReason(cube).lower()
