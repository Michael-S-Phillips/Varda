"""Derivative analyses: spectral derivative, spectral slope, spatial gradient."""

import numpy as np
import pytest

from varda.analysis.derivatives import (
    SpatialGradientAnalysis,
    SpectralDerivativeAnalysis,
    SpectralSlopeAnalysis,
)
from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource

WAVELENGTHS = np.linspace(1000.0, 2000.0, 11)  # 100 nm steps


def _linearImage(slope=2e-4, intercept=0.1) -> VardaRaster:
    cube = np.broadcast_to(
        intercept + slope * WAVELENGTHS, (4, 5, WAVELENGTHS.size)
    ).copy()
    return VardaRaster(ArrayDataSource(cube, wavelengths=WAVELENGTHS), name="scene")


def test_spectral_derivative_of_a_linear_spectrum_is_its_slope_everywhere():
    result = SpectralDerivativeAnalysis().run(
        _linearImage(slope=2e-4), lambda p, m: None
    )

    assert result.name == "scene d/dλ"
    assert result.bandCount == WAVELENGTHS.size
    np.testing.assert_array_equal(result.wavelengths, WAVELENGTHS)  # same x axis
    np.testing.assert_allclose(result.getData(), 2e-4, atol=1e-12)


def test_second_spectral_derivative_of_a_linear_spectrum_is_zero():
    analysis = SpectralDerivativeAnalysis()
    analysis.order.set(2)
    result = analysis.run(_linearImage(), lambda p, m: None)
    assert result.name == "scene d²/dλ²"
    np.testing.assert_allclose(result.getData(), 0.0, atol=1e-12)


def test_spectral_slope_between_two_wavelengths():
    analysis = SpectralSlopeAnalysis()
    analysis.startWavelength.set(1200.0)
    analysis.endWavelength.set(1800.0)

    result = analysis.run(_linearImage(slope=2e-4), lambda p, m: None)

    assert result.name == "scene slope 1200-1800"
    assert result.bandCount == 1
    np.testing.assert_allclose(result.getData()[:, :, 0], 2e-4, atol=1e-12)


def test_spectral_slope_needs_two_bands_in_the_range():
    analysis = SpectralSlopeAnalysis()
    analysis.startWavelength.set(3000.0)
    analysis.endWavelength.set(3500.0)
    with pytest.raises(ValueError, match="wavelength"):
        analysis.run(_linearImage(), lambda p, m: None)


def test_spatial_gradient_is_large_at_an_edge_and_zero_in_flat_areas():
    cube = np.zeros((10, 20, 2))
    cube[:, 10:, 1] = 1.0  # vertical step edge in band 2
    image = VardaRaster(ArrayDataSource(cube), name="scene")
    analysis = SpatialGradientAnalysis()
    analysis.band.set(2)

    result = analysis.run(image, lambda p, m: None)

    magnitude = result.getData()[:, :, 0]
    assert result.name == "scene gradient (band 2)"
    # a unit step read over the Sobel's 2-pixel baseline is 0.5 per pixel, either side
    np.testing.assert_allclose([magnitude[5, 9], magnitude[5, 10]], 0.5)
    np.testing.assert_allclose(magnitude[5, 2], 0.0)
    np.testing.assert_allclose(magnitude[5, 17], 0.0)


def test_derivative_analyses_are_filed_under_derivatives():
    for analysis in (
        SpectralDerivativeAnalysis,
        SpectralSlopeAnalysis,
        SpatialGradientAnalysis,
    ):
        assert analysis.category == "Derivatives"
