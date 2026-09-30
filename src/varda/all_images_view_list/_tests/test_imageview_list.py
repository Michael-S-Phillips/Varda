"""Tests for the interaction signals emitted by ImageListWidget."""

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QContextMenuEvent
from PyQt6.QtWidgets import QApplication

from varda.all_images_view_list.imageview_list import ImageListWidget
from varda.common.observable_list import ObservableList
from varda.utilities.debug import generate_random_image


def _showWidget(qtbot, *rasters) -> ImageListWidget:
    images = ObservableList()
    for raster in rasters:
        images.append(raster)
    widget = ImageListWidget(images)
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitExposed(widget)
    return widget


def _doubleClick(qtbot, widget: ImageListWidget, pos: QPoint) -> None:
    # Qt only emits itemDoubleClicked for an index that was already pressed, so a
    # real double-click is click-then-double-click.
    qtbot.mouseClick(widget.viewport(), Qt.MouseButton.LeftButton, pos=pos)
    qtbot.mouseDClick(widget.viewport(), Qt.MouseButton.LeftButton, pos=pos)


def _rightClick(widget: ImageListWidget, pos: QPoint) -> None:
    # The offscreen platform doesn't synthesize context-menu events from a
    # right-press, so deliver the event the platform would.
    event = QContextMenuEvent(
        QContextMenuEvent.Reason.Mouse, pos, widget.viewport().mapToGlobal(pos)
    )
    QApplication.sendEvent(widget.viewport(), event)


def test_double_click_emits_activated_with_that_image(qtbot):
    first = generate_random_image((20, 20, 10))
    second = generate_random_image((20, 20, 10))
    widget = _showWidget(qtbot, first, second)
    pos = widget.visualItemRect(widget.item(1)).center()

    with qtbot.waitSignal(widget.sigImagesActivated) as blocker:
        _doubleClick(qtbot, widget, pos)

    assert blocker.args == [[second]]


def test_right_click_emits_context_request_with_clicked_image_first(qtbot):
    first = generate_random_image((20, 20, 10))
    second = generate_random_image((20, 20, 10))
    widget = _showWidget(qtbot, first, second)
    widget.item(0).setSelected(True)
    widget.item(1).setSelected(True)
    pos = widget.visualItemRect(widget.item(1)).center()

    with qtbot.waitSignal(widget.sigContextMenuRequested) as blocker:
        _rightClick(widget, pos)

    images, _globalPos = blocker.args
    assert images == [second, first]


def test_right_click_on_empty_space_emits_nothing(qtbot):
    widget = _showWidget(qtbot, generate_random_image((20, 20, 10)))
    emptyPos = widget.viewport().rect().bottomRight() - QPoint(2, 2)
    assert widget.itemAt(emptyPos) is None

    with qtbot.assertNotEmitted(widget.sigContextMenuRequested):
        _rightClick(widget, emptyPos)
