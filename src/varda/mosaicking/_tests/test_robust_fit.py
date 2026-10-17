"""RANSAC fits keep the tie points that agree and flag the rest; manual
points always count."""

import numpy as np
import pytest
from affine import Affine
from rasterio.crs import CRS

from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.mosaicking.model import MosaicProject
from varda.mosaicking.transforms import (
    FitError,
    TransformModel,
    applyMatrix,
    ransacFit,
)

RNG = np.random.default_rng(0)
TRUE = np.array([[1.0, 0.002, 30.0], [-0.002, 1.0, -12.0], [0.0, 0.0, 1.0]])


def _points(count=60, outliers=15):
    src = RNG.uniform(0, 2000, (count, 2))
    dst = applyMatrix(TRUE, src) + RNG.normal(scale=0.2, size=(count, 2))
    bad = RNG.choice(count, outliers, replace=False)
    dst[bad] += RNG.uniform(50, 200, (outliers, 2))
    return src, dst, bad


@pytest.mark.parametrize(
    "model",
    [TransformModel.TRANSLATION, TransformModel.AFFINE, TransformModel.PROJECTIVE],
)
def test_ransac_ignores_outliers(model):
    src, dst, bad = _points()
    if model is TransformModel.TRANSLATION:
        dst = src + (30.0, -12.0) + RNG.normal(scale=0.2, size=src.shape)
        dst[bad] += 100.0
    matrix, residuals, inliers = ransacFit(model, src, dst, threshold=1.0)
    assert not inliers[bad].any()
    assert inliers.sum() == len(src) - len(bad)
    assert np.sqrt(np.mean(residuals[inliers] ** 2)) < 0.5


def test_forced_points_stay_inliers():
    src, dst, bad = _points()
    forced = np.zeros(len(src), bool)
    forced[bad[0]] = True
    _, _, inliers = ransacFit(TransformModel.AFFINE, src, dst, 1.0, forced=forced)
    assert inliers[bad[0]]


def test_too_few_points_is_an_error():
    with pytest.raises(FitError):
        ransacFit(TransformModel.AFFINE, np.zeros((2, 2)), np.zeros((2, 2)), 1.0)


def _project() -> MosaicProject:
    def image(name, x0):
        source = ArrayDataSource(
            np.zeros((50, 50, 3), np.float32),
            wavelengths=np.array([500.0, 600.0, 700.0]),
            transform=Affine(10.0, 0, x0, 0, -10.0, 1000.0),
            crs=CRS.from_epsg(32612),
        )
        return VardaRaster(source, name=name)

    return MosaicProject([image("a", 0.0), image("b", 300.0)])


def test_automatic_points_are_fitted_robustly_and_reported_per_band():
    project = _project()
    moving = project.input(1)
    # b's true position is 7 map units (0.7 px) east of where it says
    for i in range(30):
        col, row = RNG.uniform(5, 45, 2)
        x, y = moving.toMap(np.array([[col, row]]))[0] + (7.0, 0.0)
        refCol, refRow = project.input(0).fromMap(np.array([[x, y]]))[0]
        band = i % 3
        if band == 2 and i % 2:
            refCol += 6.0  # band 2 disagrees: an artifact
        project.addTiePoint(
            1, (col, row), 0, (refCol, refRow), auto=True, quality=0.95, band=band
        )
    residuals = project.fit(1, threshold=0.5)
    assert len(residuals) == 30
    assert np.allclose(moving.correction[:2, 2], (7.0, 0.0), atol=0.05)
    outliers = [p for p in project.tiePointsOf(1) if not p.inlier]
    assert outliers and all(p.band == 2 for p in outliers)
    report = project.bandReport(1)
    assert set(report) == {0, 1, 2}
    assert report[0].rms < 0.01 and report[2].inliers < report[2].count


def test_tie_point_details_survive_a_session():
    project = _project()
    project.addTiePoint(1, (1, 2), 0, (3, 4), auto=True, quality=0.9, band=2)
    restored = _project()
    restored.restore(project.state())
    point = restored.tiePoints[0]
    assert (point.auto, point.quality, point.band) == (True, 0.9, 2)


def test_old_sessions_still_load():
    project = _project()
    state = project.state()
    state["tiePoints"] = [
        {"moving": 1, "movingPixel": [1, 2], "reference": 0, "referencePixel": [3, 4]}
    ]
    project.restore(state)
    assert not project.tiePoints[0].auto and project.tiePoints[0].band is None


def test_the_phase_snr_survives_a_session():
    project = _project()
    project.addTiePoint(1, (1, 2), 0, (3, 4), auto=True, quality=0.9, phaseSnr=0.8)
    project.addTiePoint(1, (5, 6), 0, (7, 8), auto=True, quality=0.9)
    state = project.state()
    assert state["tiePoints"][1]["phaseSnr"] is None  # NaN isn't JSON
    restored = _project()
    restored.restore(state)
    assert restored.tiePoints[0].phaseSnr == 0.8
    assert np.isnan(restored.tiePoints[1].phaseSnr)
