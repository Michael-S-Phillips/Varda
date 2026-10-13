"""The Varda V mark in the main window's title area.

Native title bars only draw text, so the mark sits in a slim, fixed toolbar
at the top of the window, centred like a title. On macOS the toolbar is
unified with the title bar.
"""

from __future__ import annotations

import sys

from pathlib import Path

from PyQt6.QtCore import QEvent, QRectF, Qt
from PyQt6.QtGui import QPainter, QPalette, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QLabel, QMainWindow, QSizePolicy, QToolBar, QWidget

from varda.utilities.resources import resource_path

ICON_DIR = Path(resource_path("resources/brand/icon"))
MARK_HEIGHT = 28  # px, about the height of a title bar


def markPath(palette: QPalette) -> Path:
    """The V mark made for the palette's window colour."""
    dark = palette.color(QPalette.ColorRole.Window).lightness() < 128
    return ICON_DIR / f"varda-mark-on-{'dark' if dark else 'light'}.svg"


class MarkLabel(QLabel):
    """The V mark at ``MARK_HEIGHT``, redrawn when the palette changes."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setToolTip("Varda")
        self.setAccessibleName("Varda")
        self._path = markPath(self.palette())
        self._render()

    def currentPath(self) -> Path:
        return self._path

    def changeEvent(self, a0: QEvent | None) -> None:
        super().changeEvent(a0)
        if a0 is not None and a0.type() == QEvent.Type.PaletteChange:
            path = markPath(self.palette())
            if path != self._path:
                self._path = path
                self._render()

    def _render(self) -> None:
        path = self._path
        renderer = QSvgRenderer(str(path))
        size = renderer.defaultSize()
        width = MARK_HEIGHT * size.width() / size.height()
        ratio = self.devicePixelRatioF()
        pixmap = QPixmap(round(width * ratio), round(MARK_HEIGHT * ratio))
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer.render(painter, QRectF(0, 0, pixmap.width(), pixmap.height()))
        painter.end()
        pixmap.setDevicePixelRatio(ratio)
        self.setPixmap(pixmap)


def addTitleMarkBar(
    window: QMainWindow, hideTitleText: bool = sys.platform == "darwin"
) -> QToolBar:
    """Add the fixed V-mark bar, centred like a title, to the top of ``window``.

    On macOS the bar is unified with the title bar and the mark stands in for
    the title text, which is cleared (the Dock and menu bar still name the
    app). Elsewhere the title text stays, since taskbars show it.
    """
    bar = QToolBar("Varda", window)
    bar.setObjectName("titleMarkBar")
    bar.setMovable(False)
    bar.setFloatable(False)
    toggle = bar.toggleViewAction()
    if toggle is not None:
        toggle.setVisible(False)  # keep it out of the toolbar context menu
    bar.addWidget(_spacer(bar))
    bar.addWidget(MarkLabel(bar))
    bar.addWidget(_spacer(bar))
    window.addToolBar(Qt.ToolBarArea.TopToolBarArea, bar)
    window.setUnifiedTitleAndToolBarOnMac(True)
    if hideTitleText:
        window.setAccessibleName(window.windowTitle())
        window.setWindowTitle("")
    return bar


def _spacer(parent: QWidget) -> QWidget:
    spacer = QWidget(parent)
    spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    return spacer
