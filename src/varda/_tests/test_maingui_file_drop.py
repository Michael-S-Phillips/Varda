"""Image files can be dragged onto the main window to import them."""

import pytest
from app_model import Application
from PyQt6.QtCore import QMimeData, QPoint, QPointF, Qt, QUrl
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import QApplication

from varda.common.di_types import ProjectImages
from varda.maingui import MainGUI

APP_NAME = "varda-test-maingui-drop"
NO_BUTTONS = Qt.MouseButton.NoButton
NO_MOD = Qt.KeyboardModifier.NoModifier


@pytest.fixture
def gui(qtbot):
    app = Application(APP_NAME)
    app.images = ProjectImages()
    gui = MainGUI(app)
    qtbot.addWidget(gui)
    yield gui
    Application.destroy(APP_NAME)


def _mime(urls: list[QUrl]) -> QMimeData:
    mime = QMimeData()
    mime.setUrls(urls)
    return mime


def _dragEnter(gui, mime) -> QDragEnterEvent:
    event = QDragEnterEvent(
        QPoint(10, 10), Qt.DropAction.CopyAction, mime, NO_BUTTONS, NO_MOD
    )
    QApplication.sendEvent(gui, event)
    return event


def _drop(gui, mime) -> QDropEvent:
    # Qt delivers a Drop to the target established by the preceding DragEnter,
    # so replay the real sequence rather than sending a bare drop.
    _dragEnter(gui, mime)
    event = QDropEvent(
        QPointF(10.0, 10.0), Qt.DropAction.CopyAction, mime, NO_BUTTONS, NO_MOD
    )
    QApplication.sendEvent(gui, event)
    return event


def test_main_window_accepts_dragged_local_files(gui):
    mime = _mime([QUrl.fromLocalFile("/data/scene.img")])
    assert _dragEnter(gui, mime).isAccepted()


def test_main_window_rejects_drags_without_local_files(gui):
    mime = _mime([QUrl("https://example.com/scene.img")])
    assert not _dragEnter(gui, mime).isAccepted()


def test_dropping_local_files_emits_their_paths(gui, qtbot):
    mime = _mime([QUrl.fromLocalFile("/data/a.img"), QUrl.fromLocalFile("/data/b.tif")])
    with qtbot.waitSignal(gui.sigFilesDropped) as blocker:
        _drop(gui, mime)
    assert blocker.args == [["/data/a.img", "/data/b.tif"]]


def test_dropping_only_remote_urls_emits_nothing(gui, qtbot):
    mime = _mime([QUrl("https://example.com/scene.img")])
    with qtbot.assertNotEmitted(gui.sigFilesDropped):
        _drop(gui, mime)
