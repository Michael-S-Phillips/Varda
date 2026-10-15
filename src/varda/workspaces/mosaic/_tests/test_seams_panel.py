"""The Seams panel finds seams, shows and edits them on the mosaic, and keeps
them with the session."""

import numpy as np
import pytest
import pyqtgraph as pg
from affine import Affine
from rasterio.crs import CRS
from scipy import ndimage

from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.mosaicking.grid import defaultGrid
from varda.mosaicking.recipe import SeamMethod
from varda.mosaicking.render import renderMosaic
from varda.workspaces.mosaic.mosaic_workspace import MosaicWorkspace


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
    texture = ndimage.gaussian_filter(rng.normal(size=(60, 200)), 2.0)
    scene = np.stack([texture, 0.5 * texture], axis=2)
    widget = MosaicWorkspace(
        [_strip(scene[:, :120], 0, "A"), _strip(scene[:, 80:], 80, "B")], []
    )
    qtbot.addWidget(widget)
    return widget


def _find(workspace, qtbot, method=SeamMethod.VORONOI):
    panel = workspace.seamsPanel
    panel.method.setCurrentIndex(panel.method.findData(method))
    panel.computeButton.click()
    qtbot.waitUntil(lambda: panel.computeButton.isEnabled(), timeout=10000)
    return panel


def _sources(workspace):
    return renderMosaic(workspace.project, defaultGrid(workspace.project)).sources


def test_finding_seams_splits_the_overlap(workspace, qtbot):
    panel = _find(workspace, qtbot)
    assert "1 seam found" in panel.status.text()
    sources = _sources(workspace)
    assert (sources[:, 82:98] == 0).all() and (sources[:, 102:118] == 1).all()
    assert workspace.canvas._seamItems  # outlined on the mosaic


def test_editing_shows_draggable_outlines_that_map_back(workspace, qtbot):
    panel = _find(workspace, qtbot)
    panel.edit.setChecked(True)
    rois = [i for i in workspace.canvas._seamItems if isinstance(i, pg.PolyLineROI)]
    assert rois
    workspace.resize(1000, 700)
    workspace.show()
    qtbot.waitExposed(workspace)
    original = workspace.project.seams[0].regions[0]
    edited = []
    workspace.canvas.sigSeamEdited.connect(lambda s, r, outline: edited.append(outline))
    rois[0].sigRegionChangeFinished.emit(rois[0])  # finished without moving
    assert np.allclose(edited[0], original, atol=1e-6)


def test_an_edit_moves_the_seam(workspace, qtbot):
    _find(workspace, qtbot)
    whole = np.array([[800.0, 0.0], [2000.0, 0.0], [2000.0, 600.0], [800.0, 600.0]])
    workspace.editSeam(0, 0, whole)
    assert (_sources(workspace)[:, 81:119] == 1).all()


def test_clearing_returns_to_the_stack_order(workspace, qtbot):
    panel = _find(workspace, qtbot)
    panel.method.setCurrentIndex(panel.method.findData(SeamMethod.PRIORITY))
    panel.computeButton.click()
    assert not workspace.project.seams
    assert (_sources(workspace)[:, 80:120] == 0).all()
    assert not panel.edit.isEnabled()


def test_seams_survive_a_session(workspace, qtbot):
    _find(workspace, qtbot, SeamMethod.LEAST_DIFFERENCE)
    reopened = MosaicWorkspace(workspace.images, [])
    qtbot.addWidget(reopened)
    reopened.restoreSessionState(workspace.sessionState())
    assert reopened.seamsPanel.method.currentData() is SeamMethod.LEAST_DIFFERENCE
    assert np.array_equal(_sources(reopened), _sources(workspace))
