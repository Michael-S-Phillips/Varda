"""Texture measures: local statistics and co-occurrence (GLCM)."""

import numpy as np
import pytest

from varda.analysis.texture import (
    GlcmDirection,
    GlcmMeasure,
    LocalMeasure,
    glcmTexture,
    localStatistic,
)

RNG = np.random.default_rng(0)


def test_local_statistics_match_a_direct_computation():
    band = RNG.normal(size=(20, 20))
    window = band[5:10, 5:10]  # the 5×5 window centred on (7, 7)
    expected = {
        LocalMeasure.MEAN: window.mean(),
        LocalMeasure.VARIANCE: window.var(),
        LocalMeasure.STANDARD_DEVIATION: window.std(),
        LocalMeasure.MINIMUM: window.min(),
        LocalMeasure.MAXIMUM: window.max(),
        LocalMeasure.DATA_RANGE: np.ptp(window),
    }
    for measure, value in expected.items():
        assert localStatistic(band, measure, 5)[7, 7] == pytest.approx(value), measure
    centered = window - window.mean()
    skew = (centered**3).mean() / window.std() ** 3
    assert localStatistic(band, LocalMeasure.SKEWNESS, 5)[7, 7] == pytest.approx(skew)


def test_a_flat_band_has_no_spread_and_no_skew():
    band = np.full((10, 10), 3.0)
    for measure in (
        LocalMeasure.VARIANCE,
        LocalMeasure.DATA_RANGE,
        LocalMeasure.SKEWNESS,
    ):
        assert np.allclose(localStatistic(band, measure, 5), 0.0)


def _stripes() -> np.ndarray:
    return np.tile([0.0, 1.0], (16, 8))  # alternates every column


def test_glcm_on_a_uniform_band():
    band = np.zeros((12, 12))
    assert np.allclose(glcmTexture(band, GlcmMeasure.CONTRAST, 5), 0.0)
    assert np.allclose(glcmTexture(band, GlcmMeasure.HOMOGENEITY, 5), 1.0)
    assert np.allclose(glcmTexture(band, GlcmMeasure.SECOND_MOMENT, 5), 1.0)
    assert np.allclose(glcmTexture(band, GlcmMeasure.ENTROPY, 5), 0.0)


def test_glcm_contrast_sees_stripes_across_them_but_not_along_them():
    across = glcmTexture(
        _stripes(), GlcmMeasure.CONTRAST, 5, levels=2, direction=GlcmDirection.EAST
    )
    along = glcmTexture(
        _stripes(), GlcmMeasure.CONTRAST, 5, levels=2, direction=GlcmDirection.NORTH
    )
    assert np.allclose(
        across[2:-2, 2:-2], 1.0
    )  # every horizontal pair differs by 1 level
    assert np.allclose(along, 0.0)
    correlation = glcmTexture(
        _stripes(), GlcmMeasure.CORRELATION, 5, levels=2, direction=GlcmDirection.EAST
    )
    assert np.allclose(correlation[2:-2, 2:-2], -1.0)  # neighbors always opposite


def test_glcm_textured_areas_score_higher_than_smooth_ones():
    band = np.zeros((30, 30))
    band[:, 15:] = RNG.normal(size=(30, 15))
    contrast = glcmTexture(band, GlcmMeasure.CONTRAST, 5)
    assert contrast[:, 20:].mean() > 10 * (contrast[:, :10].mean() + 1e-9)
