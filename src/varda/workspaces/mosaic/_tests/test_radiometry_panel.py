"""The Radiometry panel balances the images, labels visual results, and
keeps its settings with the session."""

import numpy as np
import pytest
from affine import Affine
from PyQt6.QtCore import Qt
from rasterio.crs import CRS
from scipy import ndimage

from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.mosaicking.recipe import RadiometryMethod
from varda.mosaicking.grid import defaultGrid
from varda.mosaicking.render import Resampling, renderMosaic
from varda.workspaces.mosaic.mosaic_workspace import MosaicWorkspace, mosaicRaster


def _strip(cube, firstCol, name):
    source = ArrayDataSource(
        cube.astype(np.float32),
        wavelengths=np.array([500.0, 600.0]),
        wavelengthUnits="nm",
        transform=Affine(10.0, 0, firstCol * 10.0, 0, -10.0, 600.0),
        crs=CRS.from_epsg(32612),
    )
    return VardaRaster(source, name=name)


@pytest.fixture
def workspace(qtbot):
    rng = np.random.default_rng(0)
    texture = ndimage.gaussian_filter(rng.normal(size=(60, 140)), 3.0)
    scene = np.stack([0.3 + texture, 0.5 + 2 * texture], axis=2)
    left = _strip(scene[:, :80], 0, "left")
    right = _strip(scene[:, 60:] * np.array([1.25, 0.8]) + 0.05, 60, "right")
    widget = MosaicWorkspace([left, right], [left, right])
    qtbot.addWidget(widget)
    return widget


def _balance(workspace, qtbot, method):
    panel = workspace.radiometryPanel
    panel.method.setCurrentIndex(panel.method.findData(method))
    panel.balanceButton.click()
    qtbot.waitUntil(lambda: panel.balanceButton.isEnabled(), timeout=10000)
    return panel


def test_balancing_corrects_the_other_image(workspace, qtbot):
    panel = _balance(workspace, qtbot, RadiometryMethod.GLOBAL)
    correction = workspace.project.input(1).radiometry
    assert np.allclose(correction.gain, [0.8, 1.25], atol=0.01)
    assert panel.table.item(1, 1).text() != "—"
    grid = defaultGrid(workspace.project)
    result = renderMosaic(workspace.project, grid)
    raster = mosaicRaster(workspace.project, result, grid, Resampling.NEAREST)
    assert "(visual)" not in raster.name
    assert "linear, global least squares radiometry" in raster.dataSource.description


def test_histogram_matching_makes_a_visual_product(workspace, qtbot):
    _balance(workspace, qtbot, RadiometryMethod.HISTOGRAM)
    grid = defaultGrid(workspace.project)
    result = renderMosaic(workspace.project, grid)
    assert mosaicRaster(
        workspace.project, result, grid, Resampling.NEAREST
    ).name.endswith("(visual)")


def test_clearing_restores_the_original_values(workspace, qtbot):
    panel = _balance(workspace, qtbot, RadiometryMethod.GLOBAL)
    panel.method.setCurrentIndex(panel.method.findData(RadiometryMethod.NONE))
    panel.balanceButton.click()
    assert workspace.project.input(1).radiometry is None


def test_the_held_images_must_not_be_empty(workspace, qtbot):
    panel = workspace.radiometryPanel
    panel.method.setCurrentIndex(panel.method.findData(RadiometryMethod.GLOBAL))
    for row in range(panel.held.count()):
        panel.held.item(row).setCheckState(Qt.CheckState.Unchecked)
    panel.balanceButton.click()
    assert "Hold at least one" in panel.status.text()


def test_the_radiometry_survives_a_session(workspace, qtbot):
    _balance(workspace, qtbot, RadiometryMethod.GLOBAL)
    reopened = MosaicWorkspace(workspace.images, [])
    qtbot.addWidget(reopened)
    reopened.restoreSessionState(workspace.sessionState())
    panel = reopened.radiometryPanel
    assert panel.method.currentData() is RadiometryMethod.GLOBAL
    assert reopened.project.input(1).radiometry is not None
