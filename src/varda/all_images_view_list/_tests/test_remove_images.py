"""Removing images from the project: workspaces showing them close, and
anything that would be lost is confirmed first."""

import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtCore import QEvent

from varda.all_images_view_list.image_list_actions import removeImages
from varda.all_images_view_list.imageview_list import ImageListWidget
from varda.common.di_types import ProjectImages
from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.workspaces.general_image_analysis import (
    GeneralImageAnalysisConfig,
    GeneralImageAnalysisWorkflow,
)


class _Source(ArrayDataSource):
    closed = False

    def close(self) -> None:
        self.closed = True


def _image(name: str, path: str | None = "/data/x.img") -> tuple[VardaRaster, _Source]:
    data = np.random.default_rng(0).random((10, 10, 3)).astype(np.float32)
    source = _Source(data, filePath=path)
    return VardaRaster(source, name=name), source


class _FakeMainGui:
    def __init__(self, workspaces=()):
        self.childWindows = list(workspaces)
        self.closed: list[object] = []

    def closeWorkspace(self, widget) -> None:
        self.childWindows.remove(widget)
        self.closed.append(widget)


def _workspace(qtbot, images, image) -> GeneralImageAnalysisWorkflow:
    config = GeneralImageAnalysisConfig(images)
    config.image.set(image)
    workspace = GeneralImageAnalysisWorkflow(config)
    qtbot.addWidget(workspace)
    return workspace


def test_an_unused_image_on_disk_is_removed_without_asking(qtbot):
    (a, aSource), (b, _) = _image("a"), _image("b")
    images = ProjectImages([a, b])
    asked = []
    removeImages(
        [a], images, _FakeMainGui(), confirm=lambda text: asked.append(text) or True
    )
    assert list(images) == [b]
    assert asked == []
    assert aSource.closed  # its file is released


def test_workspaces_showing_the_image_close_after_confirming(qtbot):
    (a, _), (b, _) = _image("a"), _image("b")
    images = ProjectImages([a, b])
    showing, other = _workspace(qtbot, images, a), _workspace(qtbot, images, b)
    mainGui = _FakeMainGui([showing, other])
    asked = []
    removeImages([a], images, mainGui, confirm=lambda text: asked.append(text) or True)
    assert "1 workspace" in asked[0]
    assert mainGui.closed == [showing] and list(images) == [b]


def test_declining_changes_nothing(qtbot):
    a, aSource = _image("a", path=None)  # a result that was never saved
    images = ProjectImages([a])
    asked = []
    removeImages(
        [a], images, _FakeMainGui(), confirm=lambda text: asked.append(text) or False
    )
    assert "not saved" in asked[0].lower()
    assert list(images) == [a] and not aSource.closed


def test_delete_key_asks_to_remove_the_selected_images(qtbot):
    (a, _), (b, _) = _image("a"), _image("b")
    widget = ImageListWidget(ProjectImages([a, b]))
    qtbot.addWidget(widget)
    second = widget.item(1)
    assert second is not None
    second.setSelected(True)
    with qtbot.waitSignal(widget.sigRemoveRequested) as blocker:
        widget.keyPressEvent(
            QKeyEvent(
                QEvent.Type.KeyPress, Qt.Key.Key_Delete, Qt.KeyboardModifier.NoModifier
            )
        )
    assert blocker.args == [[b]]
