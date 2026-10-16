"""The 3D Terrain workspace: choices, the surface it builds, sessions and the
web page export (rendering itself needs WebGL, which offscreen test runs may
not have, so those checks are skipped there)."""

import numpy as np
import pytest
from affine import Affine
from pytestqt.exceptions import TimeoutError as QtTimeoutError
from pyproj import CRS

from varda.common.di_types import ProjectImages
from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.workspaces.terrain.terrain_workspace import (
    ELEVATION,
    PLAIN,
    StillDialog,
    TerrainWorkspace,
)
from varda.workspaces.workspace_kinds import buildWorkspace, describeWorkspace

TRANSFORM = Affine(20, 0, 0, 0, -20, 0)
CRS_ = CRS.from_user_input("+proj=eqc +R=3389500 +units=m +no_defs")


def _image(data, name) -> VardaRaster:
    return VardaRaster(
        ArrayDataSource(np.asarray(data, np.float32), transform=TRANSFORM, crs=CRS_),
        name=name,
    )


@pytest.fixture
def images():
    rows, cols = 40, 60
    yy, xx = np.mgrid[0:rows, 0:cols]
    dem = -1500 + 200 * np.exp(-((xx - 30) ** 2 + (yy - 20) ** 2) / 100.0)
    ortho = np.random.default_rng(0).random((rows, cols, 1))
    return ProjectImages([_image(dem[..., None], "dem"), _image(ortho, "ortho")])


@pytest.fixture
def workspace(qtbot, images):
    widget = TerrainWorkspace(images)
    qtbot.addWidget(widget)
    qtbot.waitUntil(lambda: widget.terrain is not None, timeout=10000)
    return widget


def test_the_dem_and_drapes_on_its_grid_are_offered(workspace, images):
    assert workspace.dem() is images[0]
    drapes = [workspace.drapeBox.itemText(i) for i in range(workspace.drapeBox.count())]
    assert drapes == [PLAIN, ELEVATION, "ortho"]
    assert workspace.terrain.heights.shape == (40, 60)
    low, high = workspace.terrain.zRange
    assert low == pytest.approx(-1500, abs=1) and high == pytest.approx(-1300, abs=1)


def test_images_loaded_later_can_be_draped(workspace, images):
    images.append(_image(np.zeros((40, 60, 3)), "color"))
    assert workspace.drapeBox.findText("color") >= 0


def test_the_web_page_export_has_controls_for_readers(workspace, tmp_path):
    workspace.drapeBox.setCurrentText("ortho")
    workspace.saveWebPage(str(tmp_path / "view.html"), None)
    html = (tmp_path / "view.html").read_text()
    assert 'id="panel"' in html and "data:image/png;base64," in html


def test_the_workspace_comes_back_from_a_session(workspace, images, qtbot):
    workspace.exaggeration.setValue(4)
    workspace.drapeBox.setCurrentText("ortho")
    workspace._keepView(
        "Crater", {"position": [0, -1, 1], "target": [0, 0, 0], "fov": 35}
    )
    described = describeWorkspace(workspace)
    assert described is not None
    kind, shown = described
    assert kind == "terrain" and shown == [images[0], images[1]]
    restored = buildWorkspace(kind, shown, images, workspace.sessionState())
    assert isinstance(restored, TerrainWorkspace)
    qtbot.addWidget(restored)
    assert restored.settings.exaggeration == 4
    assert restored.drapeImage() is images[1]
    assert list(restored.views) == ["Crater"]


def test_still_sizes(qtbot):
    dialog = StillDialog()
    qtbot.addWidget(dialog)
    assert dialog.stillSize() == (3840, 2160)
    dialog.preset.setCurrentText("Custom")
    dialog.widthBox.setValue(5000)
    assert dialog.stillSize() == (5000, 2160)


def test_a_still_renders_where_webgl_is_available(workspace, qtbot, tmp_path):
    try:
        qtbot.waitUntil(lambda: workspace.view.ready, timeout=8000)
    except QtTimeoutError:
        pytest.skip("no WebGL in this (offscreen) test run")
    workspace.saveStill(str(tmp_path / "still.png"), 800, 500, transparent=True)
    qtbot.waitUntil(lambda: (tmp_path / "still.png").exists(), timeout=10000)
    assert (tmp_path / "still.png").read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
