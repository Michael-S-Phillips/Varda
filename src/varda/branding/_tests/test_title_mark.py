"""The V mark in the main window's title area."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QMainWindow, QToolBar

from varda.branding.title_mark import (
    MARK_HEIGHT,
    MarkLabel,
    addTitleMarkBar,
    markPath,
)


def _palette(window: str) -> QPalette:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(window))
    return palette


def test_the_variant_follows_the_ground():
    assert markPath(_palette("#1e1e1e")).name == "varda-mark-on-dark.svg"
    assert markPath(_palette("#f6f4ef")).name == "varda-mark-on-light.svg"


def test_the_label_draws_the_square_mark_at_title_height(qtbot):
    label = MarkLabel()
    qtbot.addWidget(label)
    pixmap = label.pixmap()
    assert not pixmap.isNull()
    ratio = pixmap.devicePixelRatio()
    assert pixmap.height() / ratio == MARK_HEIGHT
    assert pixmap.width() == pixmap.height()
    assert label.toolTip()  # "Varda" for screen readers and hover


def test_the_label_redraws_for_a_new_palette(qtbot):
    label = MarkLabel()
    qtbot.addWidget(label)
    label.setPalette(_palette("#110d2b"))
    assert label.currentPath().name.endswith("on-dark.svg")
    label.setPalette(_palette("#ffffff"))
    assert label.currentPath().name.endswith("on-light.svg")


def test_the_bar_is_fixed_at_the_top_and_centred(qtbot):
    window = QMainWindow()
    qtbot.addWidget(window)
    bar = addTitleMarkBar(window)
    assert isinstance(bar, QToolBar)
    assert window.toolBarArea(bar) == Qt.ToolBarArea.TopToolBarArea
    assert not bar.isMovable() and not bar.isFloatable()
    label = bar.findChild(MarkLabel)
    assert label is not None
    window.resize(900, 600)
    window.show()
    qtbot.waitExposed(window)
    centre = label.mapTo(window, label.rect().center()).x()
    assert abs(centre - window.width() / 2) < 20
    assert window.unifiedTitleAndToolBarOnMac()


def test_on_macos_the_mark_replaces_the_title_text(qtbot):
    window = QMainWindow()
    qtbot.addWidget(window)
    window.setWindowTitle("Varda")
    addTitleMarkBar(window, hideTitleText=True)
    assert window.windowTitle() == ""
    assert window.accessibleName() == "Varda"  # still named for screen readers


def test_elsewhere_the_title_text_stays_for_the_taskbar(qtbot):
    window = QMainWindow()
    qtbot.addWidget(window)
    window.setWindowTitle("Varda")
    addTitleMarkBar(window, hideTitleText=False)
    assert window.windowTitle() == "Varda"
