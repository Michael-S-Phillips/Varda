"""The wordmark in the main window's title area."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QMainWindow, QToolBar

from varda.branding.wordmark import (
    MIN_HEIGHT,
    WordmarkLabel,
    addWordmarkBar,
    wordmarkPath,
)


def _palette(window: str) -> QPalette:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(window))
    return palette


def test_the_variant_follows_the_ground():
    assert wordmarkPath(_palette("#1e1e1e")).name == "varda-wordmark-small-on-dark.svg"
    assert wordmarkPath(_palette("#f6f4ef")).name == "varda-wordmark-small-on-light.svg"


def test_the_label_is_never_smaller_than_the_brand_minimum(qtbot):
    label = WordmarkLabel()
    qtbot.addWidget(label)
    pixmap = label.pixmap()
    assert not pixmap.isNull()
    assert pixmap.height() / pixmap.devicePixelRatio() >= MIN_HEIGHT
    assert label.toolTip()  # "Varda" for screen readers and hover


def test_the_label_redraws_for_a_new_palette(qtbot):
    label = WordmarkLabel()
    qtbot.addWidget(label)
    label.setPalette(_palette("#110d2b"))
    assert label.currentPath().name.endswith("on-dark.svg")
    label.setPalette(_palette("#ffffff"))
    assert label.currentPath().name.endswith("on-light.svg")


def test_the_bar_is_fixed_at_the_top_and_centred(qtbot):
    window = QMainWindow()
    qtbot.addWidget(window)
    bar = addWordmarkBar(window)
    assert isinstance(bar, QToolBar)
    assert window.toolBarArea(bar) == Qt.ToolBarArea.TopToolBarArea
    assert not bar.isMovable() and not bar.isFloatable()
    label = bar.findChild(WordmarkLabel)
    assert label is not None
    window.resize(900, 600)
    window.show()
    qtbot.waitExposed(window)
    centre = label.mapTo(window, label.rect().center()).x()
    assert abs(centre - window.width() / 2) < 20
    assert window.unifiedTitleAndToolBarOnMac()
