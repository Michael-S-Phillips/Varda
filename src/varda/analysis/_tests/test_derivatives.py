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
    np.testing.assert_allclose(result.getData()[:, :, 0], 2e-4, atol=1e-12)


def test_spectral_slope_alone_is_one_band():
    analysis = SpectralSlopeAnalysis()
    analysis.fitStatistics.set(False)
    result = analysis.run(_linearImage(slope=2e-4), lambda p, m: None)
    assert result.bandCount == 1
    np.testing.assert_allclose(result.getData()[:, :, 0], 2e-4, atol=1e-12)


def test_spectral_slope_reports_its_standard_error_and_r_squared():
    """Standard error from the residuals, sqrt(SSE / (n - 2) / Sxx), and
    R² = 1 - SSE / SST, against a direct least-squares fit."""
    rng = np.random.default_rng(7)
    cube = 0.1 + 2e-4 * WAVELENGTHS + 0.01 * rng.normal(size=(3, 4, WAVELENGTHS.size))
    image = VardaRaster(ArrayDataSource(cube, wavelengths=WAVELENGTHS), name="scene")
    result = SpectralSlopeAnalysis().run(image, lambda p, m: None)

    assert result.bandCount == 3
    assert result.bandNames == [
        "Slope 1000-2000 nm (per nm)",
        "Slope standard error (per nm)",
        "R² (unitless)",
    ]
    data = result.getData()
    y = cube[1, 2]
    x = WAVELENGTHS
    slope, intercept = np.polyfit(x, y, 1)
    residual = y - (slope * x + intercept)
    sse = np.sum(residual**2)
    se = np.sqrt(sse / (x.size - 2) / np.sum((x - x.mean()) ** 2))
    r2 = 1 - sse / np.sum((y - y.mean()) ** 2)
    np.testing.assert_allclose(data[1, 2], [slope, se, r2], rtol=1e-4)


def test_a_perfect_line_has_no_slope_error_and_r_squared_one():
    data = SpectralSlopeAnalysis().run(_linearImage(), lambda p, m: None).getData()
    np.testing.assert_allclose(data[:, :, 1], 0.0, atol=1e-9)
    np.testing.assert_allclose(data[:, :, 2], 1.0, atol=1e-6)


def test_two_bands_give_no_slope_error():
    """Two points fit exactly: there are no degrees of freedom left for the
    error, so it is NaN rather than a misleading 0."""
    analysis = SpectralSlopeAnalysis()
    analysis.startWavelength.set(1000.0)
    analysis.endWavelength.set(1100.0)
    data = analysis.run(_linearImage(), lambda p, m: None).getData()
    assert np.isnan(data[:, :, 1]).all()


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


def _image(cube, wavelengths, units, extra=None) -> VardaRaster:
    return VardaRaster(
        ArrayDataSource(
            cube,
            wavelengths=wavelengths,
            wavelengthUnits=units,
            extraMetadata=extra or {},
        ),
        name="scene",
    )


def _slopeCube():
    rng = np.random.default_rng(3)
    return rng.random((5, 6, WAVELENGTHS.size))


def test_a_micrometre_image_gives_the_same_slope_as_its_nanometre_twin():
    cube = _slopeCube()
    analysis = SpectralSlopeAnalysis()  # range in nm: 1000-2000
    nm = analysis.run(_image(cube, WAVELENGTHS, "nm"), lambda p, m: None).getData()
    um = analysis.run(
        _image(cube, WAVELENGTHS / 1000, "Micrometers"), lambda p, m: None
    ).getData()
    np.testing.assert_allclose(um, nm, equal_nan=True)


def test_the_derivative_is_per_nanometre_whatever_the_unit_and_keeps_the_axis():
    cube = _slopeCube()
    analysis = SpectralDerivativeAnalysis()
    nm = analysis.run(_image(cube, WAVELENGTHS, "nm"), lambda p, m: None)
    um = analysis.run(
        _image(cube, WAVELENGTHS / 1000, "Micrometers"), lambda p, m: None
    )
    np.testing.assert_allclose(um.getData(), nm.getData(), rtol=1e-5, equal_nan=True)
    assert um.bandModel.isSpectral
    np.testing.assert_allclose(um.bandModel.centers, WAVELENGTHS)
    assert "per nm" in um.dataSource.description


def test_bad_bands_are_left_out_of_the_slope():
    cube = _slopeCube()
    bbl = np.ones(WAVELENGTHS.size)
    inRange = np.flatnonzero((WAVELENGTHS >= 1000) & (WAVELENGTHS <= 2000))
    bbl[inRange[1]] = 0
    spoiled = cube.copy()
    spoiled[:, :, inRange[1]] = 1e6  # garbage in the bad band
    clean = cube.copy()
    keep = np.ones(WAVELENGTHS.size, bool)
    keep[inRange[1]] = False
    analysis = SpectralSlopeAnalysis()
    expected = analysis.run(
        _image(clean[:, :, keep], WAVELENGTHS[keep], "nm"), lambda p, m: None
    ).getData()
    result = analysis.run(
        _image(
            spoiled,
            WAVELENGTHS,
            "nm",
            {"bbl": "{" + ",".join(str(int(b)) for b in bbl) + "}"},
        ),
        lambda p, m: None,
    ).getData()
    np.testing.assert_allclose(result, expected, rtol=1e-6, equal_nan=True)


def test_spectral_slope_description_matches_its_defaults():
    analysis = SpectralSlopeAnalysis()
    start, end = analysis.startWavelength.get(), analysis.endWavelength.get()
    assert f"{start:g}-{end:g} nm" in SpectralSlopeAnalysis.description
    assert "µm" not in SpectralSlopeAnalysis.description
