"""Radiometric balancing recovers planted per-band gains and offsets, solves
globally over connected overlaps, and refuses images it can't reach."""

import numpy as np
import pytest
from affine import Affine
from rasterio.crs import CRS
from scipy import ndimage

from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.mosaicking.grid import defaultGrid
from varda.mosaicking.model import MosaicError, MosaicProject
from varda.mosaicking.radiometry import (
    Correction,
    LinearMode,
    RadiometryMethod,
    RadiometryQuality,
    balance,
)
from varda.mosaicking.render import renderMosaic

PIXEL = 10.0
BANDS = 3
GAINS = {1: np.array([1.2, 0.8, 1.1]), 2: np.array([0.9, 1.3, 0.7])}
OFFSETS = {1: np.array([0.05, -0.02, 0.1]), 2: np.array([-0.04, 0.03, 0.0])}


def _scene() -> np.ndarray:
    rng = np.random.default_rng(0)
    texture = ndimage.gaussian_filter(rng.normal(size=(60, 200)), 3.0)
    return np.stack([0.3 + (0.5 + b) * texture for b in range(BANDS)], axis=2)


def _strip(cube, firstCol, name):
    source = ArrayDataSource(
        cube.astype(np.float32),
        wavelengths=np.array([500.0, 600.0, 700.0]),
        wavelengthUnits="nm",
        transform=Affine(PIXEL, 0, firstCol * PIXEL, 0, -PIXEL, 600.0),
        crs=CRS.from_epsg(32612),
    )
    return VardaRaster(source, name=name)


def _project(gamma: bool = False, extra: bool = False) -> MosaicProject:
    """Three strips in a chain (A-B and B-C overlap, A and C don't); B and C
    have planted per-band gains and offsets (or B a non-linear curve)."""
    scene = _scene()
    a = _strip(scene[:, 0:80], 0, "A")
    b = (
        0.5 * np.cbrt(scene[:, 60:140]) + 0.2
        if gamma
        else scene[:, 60:140] * GAINS[1] + OFFSETS[1]
    )
    c = scene[:, 120:200] * GAINS[2] + OFFSETS[2]
    images = [a, _strip(b, 60, "B"), _strip(c, 120, "C")]
    if extra:  # far from the rest
        images.append(_strip(scene[:, 0:40], 1000, "D"))
    return MosaicProject(images)


def _undoes(correction: Correction, key: int) -> bool:
    expectedGain = 1 / GAINS[key]
    expectedOffset = -OFFSETS[key] / GAINS[key]
    return np.allclose(correction.gain, expectedGain, atol=0.01) and np.allclose(
        correction.offset, expectedOffset, atol=0.01
    )


def test_a_global_solve_recovers_the_chain():
    project = _project()
    result = balance(project, RadiometryMethod.GLOBAL, LinearMode.BOTH, held={0})
    assert _undoes(result.corrections[1], 1)
    assert _undoes(result.corrections[2], 2)  # through B: C never touches A
    assert np.allclose(result.corrections[0].gain, 1) and np.allclose(
        result.corrections[0].offset, 0
    )


def test_linear_to_the_held_image_fits_its_neighbors():
    project = _project()
    result = balance(project, RadiometryMethod.REFERENCE, LinearMode.BOTH, held={0})
    assert _undoes(result.corrections[1], 1)
    assert 2 not in result.corrections  # C doesn't overlap the held image
    assert "C" in result.message


@pytest.mark.parametrize("mode", [LinearMode.GAIN, LinearMode.OFFSET])
def test_gain_or_offset_alone(mode):
    project = _project()
    correction = balance(project, RadiometryMethod.GLOBAL, mode, held={0}).corrections[
        1
    ]
    if mode is LinearMode.GAIN:
        assert np.allclose(correction.offset, 0)
        assert not np.allclose(correction.gain, 1)
    else:
        assert np.allclose(correction.gain, 1)
        assert not np.allclose(correction.offset, 0)


def test_an_unreachable_image_is_refused():
    project = _project(extra=True)
    with pytest.raises(MosaicError, match="D"):
        balance(project, RadiometryMethod.GLOBAL, LinearMode.BOTH, held={0})


def test_holding_the_far_image_too_makes_it_solvable():
    project = _project(extra=True)
    result = balance(project, RadiometryMethod.GLOBAL, LinearMode.BOTH, held={0, 3})
    assert np.allclose(result.corrections[3].gain, 1)


def test_histogram_matching_undoes_a_nonlinear_change():
    project = _project(gamma=True)
    result = balance(project, RadiometryMethod.HISTOGRAM, LinearMode.BOTH, held={0})
    assert result.visual
    project.applyRadiometry(result)
    grid = defaultGrid(project)
    project.inputs.reverse()  # B on top, so the overlap shows B's corrected values
    mosaic = renderMosaic(project, grid).cube
    scene = _scene()
    overlap = mosaic[:, 62:78]  # columns 62-77: A and B overlap
    assert np.nanmean(np.abs(overlap - scene[:, 62:78])) < 0.01


def test_rendering_applies_the_corrections():
    project = _project()
    project.applyRadiometry(
        balance(project, RadiometryMethod.GLOBAL, LinearMode.BOTH, held={0})
    )
    mosaic = renderMosaic(project, defaultGrid(project)).cube
    assert np.nanmax(np.abs(mosaic - _scene())) < 0.01
    preview = renderMosaic(project, defaultGrid(project), bands=[2]).cube
    assert np.allclose(preview[:, :, 0], mosaic[:, :, 2], equal_nan=True)


def test_corrections_survive_a_session_and_reset():
    project = _project()
    project.applyRadiometry(
        balance(project, RadiometryMethod.GLOBAL, LinearMode.BOTH, held={0})
    )
    other = _project()
    other.restore(project.state())
    assert np.allclose(other.input(1).radiometry.gain, project.input(1).radiometry.gain)
    assert other.radiometryMethod is RadiometryMethod.GLOBAL
    other.clearRadiometry()
    assert (
        other.input(1).radiometry is None
        and other.radiometryMethod is RadiometryMethod.NONE
    )


def _quality(quality: RadiometryQuality | None) -> RadiometryQuality:
    assert quality is not None
    return quality


def test_the_fit_quality_is_reported_per_image_and_band():
    project = _project()
    result = balance(project, RadiometryMethod.GLOBAL, LinearMode.BOTH, held={0})
    quality = _quality(result.quality)
    assert set(quality.fits) == {1, 2}  # held images aren't fitted
    for fit in quality.fits.values():
        assert fit.rms.shape == fit.samples.shape == (BANDS,)
        assert (fit.samples >= 50).all() and np.all(fit.rms < 1e-3)
        assert fit.defaulted == ()
    pairs = {(o.first, o.second): o for o in quality.overlaps}
    assert set(pairs) == {(0, 1), (1, 2)}
    for overlap in pairs.values():
        assert np.all(overlap.after < 1e-3) and np.all(overlap.before > 0.01)


def test_the_rms_is_in_data_units():
    scene = _scene()
    noise = np.random.default_rng(1).normal(scale=0.01, size=(60, 80, BANDS))
    a = _strip(scene[:, 0:80], 0, "A")
    b = _strip(scene[:, 60:140] * 2.0 + noise, 60, "B")
    project = MosaicProject([a, b])
    result = balance(project, RadiometryMethod.REFERENCE, LinearMode.BOTH, held={0})
    # B's noise, divided by its gain once corrected
    assert np.allclose(_quality(result.quality).fits[1].rms, 0.005, rtol=0.25)


@pytest.mark.parametrize(
    "method", [RadiometryMethod.REFERENCE, RadiometryMethod.GLOBAL]
)
def test_bands_without_enough_samples_are_listed(method):
    scene = _scene()
    b = scene[:, 60:140] * GAINS[1] + OFFSETS[1]
    b[:, :, 2] = np.nan  # no band 3 anywhere in B
    project = MosaicProject([_strip(scene[:, 0:80], 0, "A"), _strip(b, 60, "B")])
    result = balance(project, method, LinearMode.BOTH, held={0})
    fit = _quality(result.quality).fits[1]
    assert fit.defaulted == (2,) and fit.samples[2] == 0
    assert result.corrections[1].gain[2] == 1 and result.corrections[1].offset[2] == 0
    assert "band 3" in result.message


def test_histogram_matching_reports_its_agreement_too():
    project = _project(gamma=True)
    result = balance(project, RadiometryMethod.HISTOGRAM, LinearMode.BOTH, held={0})
    overlap = next(
        o for o in _quality(result.quality).overlaps if (o.first, o.second) == (0, 1)
    )
    assert np.all(overlap.after < overlap.before)


def test_the_quality_survives_a_session_and_is_cleared():
    project = _project()
    project.applyRadiometry(
        balance(project, RadiometryMethod.GLOBAL, LinearMode.BOTH, held={0})
    )
    state = project.state()
    assert state["radiometry"]["quality"]["fits"]
    other = _project()
    other.restore(state)
    restored = _quality(other.radiometryQuality)
    assert np.allclose(
        restored.fits[1].rms, _quality(project.radiometryQuality).fits[1].rms
    )
    assert len(restored.overlaps) == 2
    other.clearRadiometry()
    assert other.radiometryQuality is None
