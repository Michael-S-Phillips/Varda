"""A selected thumbnail must be unmistakably marked."""

from PyQt6.QtCore import QPoint
from PyQt6.QtGui import QColor

from varda.all_images_view_list.imageview_list import ImageListWidget
from varda.common.observable_list import ObservableList
from varda.utilities.debug import generate_random_image


def _borderPixel(widget: ImageListWidget) -> QColor:
    # On the item's left edge, below the 64px thumbnail (so untouched by any
    # thumbnail-only tint) and clear of the frame's rounded corner.
    rect = widget.visualItemRect(widget.item(0))
    image = widget.viewport().grab().toImage()
    return image.pixelColor(rect.bottomLeft() + QPoint(2, -10))


def _isClose(a: QColor, b: QColor, tolerance: int = 40) -> bool:
    return all(
        abs(x - y) <= tolerance
        for x, y in ((a.red(), b.red()), (a.green(), b.green()), (a.blue(), b.blue()))
    )


def test_selected_item_is_framed_in_the_highlight_colour(qtbot):
    images = ObservableList()
    images.append(generate_random_image((20, 20, 10)))
    widget = ImageListWidget(images)
    qtbot.addWidget(widget)
    widget.show()
    qtbot.waitExposed(widget)
    highlight = widget.palette().highlight().color()

    unselected = _borderPixel(widget)
    widget.item(0).setSelected(True)
    selected = _borderPixel(widget)

    assert not _isClose(unselected, highlight)
    assert _isClose(selected, highlight)
