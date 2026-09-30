"""Shannon entropy analyses: per-pixel spectral entropy and local spatial entropy."""

import numpy as np

from varda.analysis.statistics import SpatialEntropyAnalysis, SpectralEntropyAnalysis
from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource


def _image(cube, nodata=None) -> VardaRaster:
    return VardaRaster(ArrayDataSource(cube, nodata=nodata), name="scene")


def test_spectral_entropy_is_maximal_for_flat_and_zero_for_one_hot_spectra():
    cube = np.zeros((2, 2, 8))
    cube[0, 0, :] = 0.5  # flat spectrum: log2(8) = 3 bits
    cube[0, 1, 3] = 1.0  # one-hot spectrum: 0 bits
    cube[1, 0, :] = -1.0  # nodata pixel
    cube[1, 1, :] = [1, 1, 0, 0, 0, 0, 0, 0]  # two equal bands: 1 bit

    result = SpectralEntropyAnalysis().run(_image(cube, nodata=-1.0), lambda p, m: None)

    values = result.getData()[:, :, 0]
    assert result.name == "scene spectral entropy"
    assert result.bandCount == 1
    np.testing.assert_allclose(values[0, 0], 3.0)
    np.testing.assert_allclose(values[0, 1], 0.0)
    np.testing.assert_allclose(values[1, 1], 1.0)
    assert np.isnan(values[1, 0])


def test_spatial_entropy_is_zero_on_a_constant_band_and_about_one_bit_on_a_checkerboard():
    rows, cols = np.indices((20, 20))
    checkerboard = ((rows + cols) % 2).astype(float)
    cube = np.stack([np.full((20, 20), 0.3), checkerboard], axis=2)

    analysis = SpatialEntropyAnalysis()
    analysis.window.set(3)

    analysis.band.set(1)
    constant = analysis.run(_image(cube), lambda p, m: None).getData()[:, :, 0]
    np.testing.assert_allclose(constant, 0.0, atol=1e-9)

    analysis.band.set(2)
    checker = analysis.run(_image(cube), lambda p, m: None).getData()[:, :, 0]
    # a 3x3 window holds 5 of one value and 4 of the other: H = 0.991 bits
    np.testing.assert_allclose(checker[5:15, 5:15], 0.9911, atol=1e-3)


def test_spatial_entropy_names_the_band_and_ignores_nodata():
    cube = np.random.default_rng(0).random((10, 10, 2))
    cube[0, 0, :] = -1.0
    analysis = SpatialEntropyAnalysis()
    analysis.band.set(2)

    result = analysis.run(_image(cube, nodata=-1.0), lambda p, m: None)

    assert result.name == "scene spatial entropy (band 2)"
    assert np.isnan(result.getData()[0, 0, 0])
    assert np.isfinite(result.getData()[5, 5, 0])


def test_entropy_analyses_are_filed_under_statistics():
    for analysis in (SpectralEntropyAnalysis, SpatialEntropyAnalysis):
        assert analysis.category == "Statistics"
