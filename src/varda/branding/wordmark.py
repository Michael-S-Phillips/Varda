"""The Varda wordmark in the main window's title area.

Native title bars only draw text, so the wordmark sits in a slim, fixed
toolbar at the top of the window. On macOS the toolbar is unified with the
title bar. The brand guide's minimum height for the small wordmark is 30 px,
so it is drawn at exactly that size.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QEvent, QRectF, Qt
from PyQt6.QtGui import QPainter, QPalette, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QLabel, QMainWindow, QSizePolicy, QToolBar, QWidget

from varda.utilities.resources import resource_path

WORDMARK_DIR = Path(resource_path("resources/brand/wordmark"))
MIN_HEIGHT = 30  # px; the small (no dots) wordmark is for 30-60 px


def wordmarkPath(palette: QPalette) -> Path:
    """The small wordmark made for the palette's window colour."""
    dark = palette.color(QPalette.ColorRole.Window).lightness() < 128
    return WORDMARK_DIR / f"varda-wordmark-small-on-{'dark' if dark else 'light'}.svg"


class WordmarkLabel(QLabel):
    """The wordmark at ``MIN_HEIGHT``, redrawn when the palette changes."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setToolTip("Varda")
        self.setAccessibleName("Varda")
        self._path = wordmarkPath(self.palette())
        self._render()

    def currentPath(self) -> Path:
        return self._path

    def changeEvent(self, a0: QEvent | None) -> None:
        super().changeEvent(a0)
        if a0 is not None and a0.type() == QEvent.Type.PaletteChange:
            path = wordmarkPath(self.palette())
            if path != self._path:
                self._path = path
                self._render()

    def _render(self) -> None:
        path = self._path
        renderer = QSvgRenderer(str(path))
        size = renderer.defaultSize()
        width = MIN_HEIGHT * size.width() / size.height()
        ratio = self.devicePixelRatioF()
        pixmap = QPixmap(round(width * ratio), round(MIN_HEIGHT * ratio))
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer.render(painter, QRectF(0, 0, pixmap.width(), pixmap.height()))
        painter.end()
        pixmap.setDevicePixelRatio(ratio)
        self.setPixmap(pixmap)


def addWordmarkBar(window: QMainWindow) -> QToolBar:
    """Add the fixed wordmark bar, centred like a title, to the top of ``window``."""
    bar = QToolBar("Varda", window)
    bar.setObjectName("wordmarkBar")
    bar.setMovable(False)
    bar.setFloatable(False)
    toggle = bar.toggleViewAction()
    if toggle is not None:
        toggle.setVisible(False)  # keep it out of the toolbar context menu
    bar.addWidget(_spacer(bar))
    bar.addWidget(WordmarkLabel(bar))
    bar.addWidget(_spacer(bar))
    window.addToolBar(Qt.ToolBarArea.TopToolBarArea, bar)
    window.setUnifiedTitleAndToolBarOnMac(True)
    return bar


def _spacer(parent: QWidget) -> QWidget:
    spacer = QWidget(parent)
    spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    return spacer
