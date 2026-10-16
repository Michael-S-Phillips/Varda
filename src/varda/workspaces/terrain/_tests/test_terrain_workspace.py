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
from varda.utilities.debug import generate_perlin_noise_3d
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


def _offsetOverlay(images, size=(40, 60)):
    """An overlay of the DEM's own texture whose georeferencing is 60 m east
    and 40 m south of the truth (an orthoimage on the DEM's grid holds the
    texture)."""
    rows, cols = size
    texture = generate_perlin_noise_3d((rows, cols, 2), (rows // 10, cols // 10, 2))
    texture = texture[:, :, :1].astype(np.float32)
    images.append(_image(texture, "ortho"))
    top, left = rows // 8, cols // 8
    overlay = VardaRaster(
        ArrayDataSource(
            np.repeat(texture[top:-top, left:-left], 3, axis=2),
            transform=Affine(20, 0, left * 20 + 60, 0, -20, -top * 20 - 40),
            crs=CRS_,
        ),
        name="crism",
    )
    images.append(overlay)
    return overlay


def test_an_overlay_is_draped_and_auto_aligned(qtbot):
    rows, cols = 240, 320
    yy, xx = np.mgrid[0:rows, 0:cols]
    dem = -1500 + 100 * np.sin(xx / 30.0) * np.cos(yy / 25.0)
    images = ProjectImages([_image(dem[..., None], "dem")])
    overlay = _offsetOverlay(images, (rows, cols))
    workspace = TerrainWorkspace(images, images[0])
    qtbot.addWidget(workspace)
    assert overlay in workspace._overlayCandidates()
    added = workspace.overlayPanel.add(overlay)
    assert added.reference == "ortho"  # the first one-band image on the DEM's grid
    qtbot.waitUntil(lambda: len(workspace._overlays) == 1, timeout=10000)
    west, south, east, north = workspace._overlays[0].uvBounds
    assert 0 <= west < east <= 1 and 0 <= south < north <= 1
    workspace.autoAlign(0)
    qtbot.waitUntil(lambda: added.alignment.points > 0, timeout=30000)
    moved = added.alignment.correct(np.array([[3000.0, -2400.0]]))[0]
    assert moved == pytest.approx([3000 - 60, -2400 + 40], abs=4)


def test_overlays_come_back_from_a_session(workspace, images, qtbot):
    overlay = _offsetOverlay(images)
    added = workspace.overlayPanel.add(overlay)
    added.opacity = 0.4
    added.alignment.shift = (12.0, -3.0)
    described = describeWorkspace(workspace)
    assert described is not None
    kind, shown = described
    assert shown[-1] is overlay
    restored = buildWorkspace(kind, shown, images, workspace.sessionState())
    assert isinstance(restored, TerrainWorkspace)
    qtbot.addWidget(restored)
    (back,) = restored.overlayPanel.overlays
    assert back.image is overlay and back.opacity == 0.4
    assert back.alignment.shift == (12.0, -3.0)
