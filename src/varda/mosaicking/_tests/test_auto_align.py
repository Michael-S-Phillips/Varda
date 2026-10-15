"""Automatic alignment recovers planted misregistrations between strips."""

import numpy as np
import pytest
from affine import Affine
from rasterio.crs import CRS
from scipy import ndimage

from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.mosaicking.matching import MatchMethod, MatchSettings, autoAlign
from varda.mosaicking.model import MosaicProject
from varda.mosaicking.transforms import TransformModel

PIXEL = 18.0
ROWS, COLS, BANDS = 240, 320, 6
LEFT, RIGHT = (0, 200), (120, 320)  # columns; 80 px of overlap


def _scene(seed=0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    texture = ndimage.gaussian_filter(rng.normal(size=(ROWS, COLS)), 2.0)
    gains = np.linspace(0.5, 1.5, BANDS)
    noise = np.linspace(0.002, 0.2, BANDS)  # the last bands are noisy
    return np.stack(
        [
            0.3 + g * texture + rng.normal(scale=s, size=texture.shape)
            for g, s in zip(gains, noise)
        ],
        axis=2,
    )


def _moved(cube: np.ndarray, dx: float, dy: float) -> np.ndarray:
    spectrum = np.fft.fft2(cube, axes=(0, 1))
    shifted = ndimage.fourier_shift(spectrum, (dy, dx, 0))
    return np.real(np.fft.ifft2(shifted, axes=(0, 1)))


def _image(cube: np.ndarray, firstCol: int, name: str) -> VardaRaster:
    transform = Affine(PIXEL, 0, 500000.0 + firstCol * PIXEL, 0, -PIXEL, 4000000.0)
    source = ArrayDataSource(
        cube.astype(np.float32),
        wavelengths=np.linspace(1000, 2500, BANDS),
        wavelengthUnits="nm",
        transform=transform,
        crs=CRS.from_epsg(32612),
    )
    return VardaRaster(source, name=name)


def _project(movingCube: np.ndarray) -> MosaicProject:
    scene = _scene()
    left = _image(scene[:, slice(*LEFT)], LEFT[0], "left")
    right = _image(movingCube[:, slice(*RIGHT)], RIGHT[0], "right")
    return MosaicProject([left, right])


@pytest.mark.parametrize("refine", [True, False])
def test_a_planted_shift_is_recovered(refine):
    dx, dy = 2.3, -1.6  # the right strip's content sits this far off
    project = _project(_moved(_scene(), dx, dy))
    result = autoAlign(project, 1, [0], MatchSettings(refine=refine))
    assert result.added > 10
    project.fit(1)
    expected = (-dx * PIXEL, dy * PIXEL)  # the correction undoes it (map y is up)
    tolerance = 0.05 if refine else 0.15
    assert np.allclose(
        project.input(1).correction[:2, 2], expected, atol=tolerance * PIXEL
    )


def test_the_noisy_bands_are_not_chosen():
    project = _project(_scene())
    result = autoAlign(project, 1, [0], MatchSettings(bandCount=3))
    assert len(result.bands) == 3
    assert BANDS - 1 not in result.bands  # the noisiest
    assert {p.band for p in project.tiePoints} <= set(result.bands)


def test_matching_again_replaces_the_automatic_points_only():
    project = _project(_scene())
    project.addTiePoint(1, (5, 5), 0, (125, 5))
    autoAlign(project, 1, [0], MatchSettings(bandCount=1))
    first = len(project.tiePoints)
    autoAlign(project, 1, [0], MatchSettings(bandCount=1))
    assert len(project.tiePoints) == first
    assert sum(not p.auto for p in project.tiePoints) == 1


def test_the_displacement_field_shows_the_shift():
    dx, dy = 3.0, 0.0
    project = _project(_moved(_scene(), dx, dy))
    result = autoAlign(project, 1, [0], MatchSettings(bandCount=2))
    field = result.fields[0]
    assert field.dx.shape == field.dy.shape == field.quality.shape
    finite = np.isfinite(field.dx)
    assert finite.sum() > 10
    assert np.allclose(np.nanmedian(field.dx), dx * PIXEL, atol=0.1 * PIXEL)
    assert np.allclose(np.nanmedian(field.dy), 0.0, atol=0.1 * PIXEL)
    # the field's grid lies over the overlap
    x, _ = field.transform * (0.5, 0.5)
    assert 500000.0 + RIGHT[0] * PIXEL <= x <= 500000.0 + LEFT[1] * PIXEL


def test_features_handle_a_rotation():
    """Phase correlation can't follow a 4° rotation; ORB features can."""
    scene = _scene()
    rotated = np.stack(
        [
            ndimage.rotate(scene[:, :, b], 4.0, reshape=False, order=3, mode="reflect")
            for b in range(BANDS)
        ],
        axis=2,
    )
    project = _project(rotated)
    project.input(1).model = TransformModel.SIMILARITY
    result = autoAlign(
        project, 1, [0], MatchSettings(method=MatchMethod.FEATURES, bandCount=1)
    )
    assert result.method is MatchMethod.FEATURES
    assert result.added >= 10
    project.fit(1, threshold=2.0)
    matrix = project.input(1).correction
    angle = np.degrees(np.arctan2(matrix[1, 0], matrix[0, 0]))
    assert abs(abs(angle) - 4.0) < 0.5


def test_unrelated_images_give_no_confident_points():
    project = _project(_scene(seed=5))  # a different scene: nothing matches
    result = autoAlign(
        project, 1, [0], MatchSettings(method=MatchMethod.PHASE, bandCount=2)
    )
    assert result.added < 5


def test_images_that_do_not_overlap_are_reported():
    project = _project(_scene())
    project.nudge(1, 10000.0, 0.0)
    result = autoAlign(project, 1, [0], MatchSettings())
    assert result.added == 0 and "overlap" in result.message.lower()


def _plantedMatcher(shift):
    """A stand-in for the PyTorch worker's matchers: a grid of points, each
    found ``shift`` pixels off in the moving image."""
    calls = []

    def match(reference, moving, method):
        calls.append((reference.shape, method))
        ys, xs = np.mgrid[
            10 : reference.shape[0] - 10 : 15, 10 : reference.shape[1] - 10 : 15
        ]
        first = np.column_stack([xs.ravel(), ys.ravel()]).astype(float) + 0.5
        return first, first + shift, np.full(len(first), 0.9)

    return match, calls


@pytest.mark.parametrize("method", [MatchMethod.LOFTR, MatchMethod.SIFT])
def test_external_matchers_are_pooled_over_the_bands(method):
    project = _project(_scene())
    matcher, calls = _plantedMatcher(np.array([2.0, -1.0]))
    result = autoAlign(
        project,
        1,
        [0],
        MatchSettings(method=method, bandCount=2, externalMatcher=matcher),
    )
    assert result.method is method
    assert [m for _, m in calls] == [
        {MatchMethod.LOFTR: "loftr", MatchMethod.SIFT: "sift"}[method]
    ] * 2
    assert result.added > 20 and {p.band for p in project.tiePoints} == set(
        result.bands
    )
    assert all(p.quality == pytest.approx(0.9) for p in project.tiePoints)
    project.fit(1)
    # 2 px east, 1 px north in the moving image: the correction undoes it
    assert np.allclose(
        project.input(1).correction[:2, 2], (-2 * PIXEL, -1 * PIXEL), atol=1e-6
    )


def test_external_matchers_need_the_runtime():
    with pytest.raises(RuntimeError, match="PyTorch"):
        autoAlign(_project(_scene()), 1, [0], MatchSettings(method=MatchMethod.LOFTR))
