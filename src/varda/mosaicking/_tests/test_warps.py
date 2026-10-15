"""Polynomial and thin-plate-spline warps: fitted to tie points, inverted,
saved, and used when rendering."""

import numpy as np
import pytest
from affine import Affine
from rasterio.crs import CRS
from scipy import ndimage

from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.mosaicking.grid import TargetGrid
from varda.mosaicking.model import MosaicProject
from varda.mosaicking.render import rawPixels, renderMosaic
from varda.mosaicking.transforms import (
    MIN_POINTS,
    FitError,
    TransformModel,
    Warp,
    fitWarp,
    robustWarpFit,
)

RNG = np.random.default_rng(0)


def _quadratic(points: np.ndarray) -> np.ndarray:
    x, y = points[:, 0], points[:, 1]
    return np.column_stack(
        [5 + 1.01 * x + 2e-5 * x * y - 1e-5 * y**2, -3 + 0.99 * y + 1.5e-5 * x**2]
    )


def _bump(points: np.ndarray) -> np.ndarray:
    """A smooth local distortion of up to 4 units around (500, 500)."""
    d = np.exp(-np.sum((points - 500.0) ** 2, axis=1) / (2 * 150.0**2))
    return points + np.column_stack([4 * d, -3 * d])


@pytest.mark.parametrize(
    "model", [TransformModel.POLYNOMIAL2, TransformModel.POLYNOMIAL3]
)
def test_a_polynomial_recovers_a_polynomial_distortion(model):
    src = RNG.uniform(0, 1000, (40, 2))
    warp, residuals = fitWarp(model, src, _quadratic(src))
    assert residuals.max() < 1e-6
    test = RNG.uniform(100, 900, (20, 2))
    assert np.allclose(warp.forward(test), _quadratic(test), atol=1e-6)
    assert np.allclose(warp.inverse(_quadratic(test)), test, atol=1e-6)


def test_a_thin_plate_spline_follows_a_local_distortion():
    grid = np.stack(
        np.meshgrid(np.linspace(0, 1000, 9), np.linspace(0, 1000, 9)), -1
    ).reshape(-1, 2)
    warp, residuals = fitWarp(TransformModel.TPS, grid, _bump(grid))
    assert residuals.max() < 0.1
    test = RNG.uniform(100, 900, (50, 2))
    tpsError = np.abs(warp.forward(test) - _bump(test)).max()
    affine, _ = fitWarp(TransformModel.POLYNOMIAL2, grid, _bump(grid))
    assert tpsError < 0.3 < np.abs(affine.forward(test) - _bump(test)).max()
    assert np.allclose(warp.inverse(warp.forward(test)), test, atol=1e-3)


def test_too_few_points_is_an_error():
    with pytest.raises(FitError, match="at least"):
        fitWarp(TransformModel.POLYNOMIAL3, np.zeros((5, 2)), np.zeros((5, 2)))
    assert MIN_POINTS[TransformModel.POLYNOMIAL2] == 6


def test_robust_fits_leave_out_outliers():
    src = RNG.uniform(0, 1000, (80, 2))
    bad = RNG.choice(80, 10, replace=False)
    for model, distortion in (
        (TransformModel.POLYNOMIAL3, _quadratic),
        (TransformModel.TPS, _bump),
    ):
        dst = distortion(src)
        dst[bad] += 60.0
        warp, residuals, inliers = robustWarpFit(model, src, dst, threshold=1.0)
        assert not inliers[bad].any(), model
        assert inliers.sum() >= 65, model
        assert np.sqrt(np.mean(residuals[inliers] ** 2)) < 0.5, model


def test_a_warp_survives_saving():
    src = RNG.uniform(0, 1000, (30, 2))
    warp, _ = fitWarp(TransformModel.TPS, src, _bump(src))
    restored = Warp.fromState(warp.state())
    test = RNG.uniform(0, 1000, (10, 2))
    assert np.allclose(restored.forward(test), warp.forward(test))


# --- in a mosaic ---------------------------------------------------------------

PIXEL = 10.0


def _pixelBump(pixels: np.ndarray) -> np.ndarray:
    """Where each moving pixel's content really is: up to 3 px off around the
    image's center."""
    d = np.exp(-np.sum((pixels - 60.0) ** 2, axis=1) / (2 * 20.0**2))
    return pixels + np.column_stack([3 * d, -2 * d])


def _images():
    """A reference and a moving image whose content is warped by a bump."""
    texture = ndimage.gaussian_filter(RNG.normal(size=(120, 120)), 2.0).astype(
        np.float32
    )
    rows, cols = np.mgrid[:120, :120] + 0.5
    pixels = np.column_stack([cols.ravel(), rows.ravel()])
    # sample the texture where the bump sends each moving pixel (in pixel units)
    source = _pixelBump(pixels) - 0.5
    warped = ndimage.map_coordinates(
        texture, [source[:, 1], source[:, 0]], order=3, mode="nearest"
    )

    def image(cube, name):
        return VardaRaster(
            ArrayDataSource(
                cube.reshape(120, 120, 1),
                wavelengths=np.array([600.0]),
                transform=Affine(PIXEL, 0, 0, 0, -PIXEL, 1200.0),
                crs=CRS.from_epsg(32612),
            ),
            name=name,
        )

    return (
        image(texture, "reference"),
        image(warped.astype(np.float32), "moving"),
        pixels,
    )


def _unbump(pixels: np.ndarray) -> np.ndarray:
    """The moving pixel whose content belongs at ``pixels`` (inverse bump)."""
    guess = pixels.copy()
    for _ in range(50):
        guess = guess + (pixels - _pixelBump(guess))
    return guess


def test_a_thin_plate_spline_aligns_a_warped_image():
    """Each output pixel samples the moving image where its content really is:
    within a fraction of a pixel with the spline, far off with an affine."""
    reference, moving, _ = _images()
    project = MosaicProject([reference, moving])
    lattice = np.stack(
        np.meshgrid(np.linspace(5, 115, 12), np.linspace(5, 115, 12)), -1
    ).reshape(-1, 2)
    for p in lattice:
        project.addTiePoint(1, p, 0, _pixelBump(p[None])[0])
    grid = TargetGrid(
        reference.transform, reference.width, reference.height, reference.crs
    )
    rows = slice(10, 110)
    x, y = grid.pixelCenters(rows)
    inner = (x > 100) & (x < 1100)  # columns 10-110
    truth = _unbump(np.column_stack(~reference.transform * (x[inner], y[inner])))

    def worst(model: TransformModel) -> float:
        project.input(1).model = model
        project.fit(1)
        cols, rowsIn = rawPixels(project.input(1), grid, rows)
        return float(
            np.abs(np.column_stack([cols[inner], rowsIn[inner]]) - truth).max()
        )

    assert worst(TransformModel.TPS) < 0.15  # the warp's 8 px lattice limits it
    assert worst(TransformModel.AFFINE) > 1.0
    assert project.input(1).warp is None


def test_rendering_follows_the_warp():
    reference, moving, _ = _images()
    project = MosaicProject([reference, moving])
    lattice = np.stack(
        np.meshgrid(np.linspace(5, 115, 12), np.linspace(5, 115, 12)), -1
    ).reshape(-1, 2)
    for p in lattice:
        project.addTiePoint(1, p, 0, _pixelBump(p[None])[0])
    project.input(1).model = TransformModel.TPS
    project.fit(1)
    project.input(0).visible = False
    grid = TargetGrid(
        reference.transform, reference.width, reference.height, reference.crs
    )
    result = renderMosaic(project, grid, visibleOnly=True)
    cols, rows = rawPixels(project.input(1), grid, slice(0, grid.height))
    inside = (cols >= 0) & (cols < 120) & (rows >= 0) & (rows < 120)
    expected = moving.getData()[rows[inside].astype(int), cols[inside].astype(int), 0]
    assert np.array_equal(result.cube[:, :, 0].ravel()[inside], expected)


def test_pixels_and_map_round_trip_through_a_warp():
    reference, moving, _ = _images()
    project = MosaicProject([reference, moving])
    lattice = np.stack(
        np.meshgrid(np.linspace(5, 115, 6), np.linspace(5, 115, 6)), -1
    ).reshape(-1, 2)
    for p in lattice:
        project.addTiePoint(1, p, 0, _pixelBump(p[None])[0])
    project.input(1).model = TransformModel.POLYNOMIAL3
    project.fit(1)
    item = project.input(1)
    pixels = RNG.uniform(10, 110, (10, 2))
    assert np.allclose(item.fromMap(item.toMap(pixels)), pixels, atol=0.05)
    project.nudge(1, 20.0, 0.0)  # a nudge after a warp shifts the result
    assert np.allclose(
        item.toMap(pixels)[:, 0] - 20.0, project.input(1).toMap(pixels)[:, 0] - 20.0
    )
    state = project.state()
    other = MosaicProject([reference, moving])
    other.restore(state)
    assert np.allclose(other.input(1).toMap(pixels), item.toMap(pixels))
    project.resetAlignment(1)
    assert item.warp is None
