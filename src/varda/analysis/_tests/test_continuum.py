"""Continuum removal over a whole image: each spectrum divided by its upper hull."""

import numpy as np
import pytest

from varda.analysis.continuum import ContinuumRemovalAnalysis, continuumRemovedCube
from varda.analysis.registry import ANALYSES
from varda.analysis.spectral_library import continuumRemoved
from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource

WL = np.linspace(1000.0, 2500.0, 61)


def _cube():
    rng = np.random.default_rng(0)
    base = 0.4 + 0.1 * (WL - 1000) / 1500
    dip = 0.15 * np.exp(-0.5 * ((WL - 2200) / 30) ** 2)
    cube = (base - dip) * (1 + 0.05 * rng.random((6, 7, 1))) + 0.01 * rng.random(
        (6, 7, WL.size)
    )
    cube[0, 0, :] = np.nan
    return cube


def test_every_pixel_matches_the_single_spectrum_continuum_removal():
    cube = _cube()
    out = continuumRemovedCube(cube, WL)
    for r, c in [(1, 1), (3, 5), (5, 6)]:
        np.testing.assert_allclose(
            out[r, c], continuumRemoved(WL, cube[r, c]), rtol=1e-10
        )
    assert np.isnan(out[0, 0]).all()
    assert np.nanmax(out) <= 1.0 + 1e-12


def _image(units="nm", scale=1.0):
    return VardaRaster(
        ArrayDataSource(_cube(), wavelengths=WL / scale, wavelengthUnits=units),
        name="scene",
    )


def test_the_analysis_works_in_a_window_and_keeps_its_wavelengths():
    analysis = ContinuumRemovalAnalysis()
    analysis.startWavelength.set(2000.0)
    analysis.endWavelength.set(2400.0)
    result = analysis.run(_image(), lambda p, m: None)
    keep = (WL >= 2000) & (WL <= 2400)
    assert result.bandCount == keep.sum()
    np.testing.assert_allclose(result.bandModel.centers, WL[keep])
    dip = int(np.argmin(np.abs(WL[keep] - 2200)))
    assert np.nanmedian(result.getData()[:, :, dip]) < 0.8


def test_a_micrometre_image_gives_the_same_result():
    analysis = ContinuumRemovalAnalysis()
    nm = analysis.run(_image(), lambda p, m: None).getData()
    um = analysis.run(_image("Micrometers", 1000.0), lambda p, m: None).getData()
    np.testing.assert_allclose(um, nm, equal_nan=True)


def test_it_is_offered_with_the_spectral_parameters():
    assert ContinuumRemovalAnalysis in ANALYSES
    assert ContinuumRemovalAnalysis.category == "Spectral Parameters"


def test_an_image_without_wavelengths_is_refused():
    image = VardaRaster(ArrayDataSource(np.ones((3, 3, 4))), name="bands")
    with pytest.raises(ValueError, match="wavelengths"):
        ContinuumRemovalAnalysis().run(image, lambda p, m: None)
