"""The Varda V mark in the main window's title area.

Native title bars only draw text, so the mark sits in a slim, fixed toolbar
at the top of the window, centred like a title.

On macOS the window's content extends under the title bar (Qt's
MaximizeUsingFullscreenGeometryHint sets AppKit's full-size content view) and
the bar takes the title strip itself, beside the traffic-light buttons. The
title text is cleared, and the bar moves the window when dragged and zooms
it when double-clicked, as the title bar did. Elsewhere the bar sits under a
normal title bar, whose text the taskbar shows.
"""

from __future__ import annotations

import sys

from pathlib import Path

from PyQt6.QtCore import QEvent, QRectF, Qt
from PyQt6.QtGui import QMouseEvent, QPainter, QPalette, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QLabel, QMainWindow, QSizePolicy, QToolBar, QWidget

from varda.utilities.resources import resource_path

ICON_DIR = Path(resource_path("resources/brand/icon"))
MARK_HEIGHT = 28  # px, under a normal title bar
TITLE_BAR_HEIGHT = 28  # px, macOS's title strip, which the bar fills there
MERGED_MARK_HEIGHT = 20  # px, with room around it inside the strip


def markPath(palette: QPalette) -> Path:
    """The V mark made for the palette's window colour."""
    dark = palette.color(QPalette.ColorRole.Window).lightness() < 128
    return ICON_DIR / f"varda-mark-on-{'dark' if dark else 'light'}.svg"


class MarkLabel(QLabel):
    """The V mark at ``height`` px, redrawn when the palette changes."""

    def __init__(self, parent: QWidget | None = None, height: int = MARK_HEIGHT):
        super().__init__(parent)
        self._height = height
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
        width = self._height * size.width() / size.height()
        ratio = self.devicePixelRatioF()
        pixmap = QPixmap(round(width * ratio), round(self._height * ratio))
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer.render(painter, QRectF(0, 0, pixmap.width(), pixmap.height()))
        painter.end()
        pixmap.setDevicePixelRatio(ratio)
        self.setPixmap(pixmap)


class TitleMarkBar(QToolBar):
    """The fixed bar holding the mark. Merged into the macOS title strip, it
    also moves the window when dragged and zooms it when double-clicked."""

    def __init__(self, window: QMainWindow, merged: bool):
        super().__init__("Varda", window)
        self._window = window
        self.merged = merged
        self.setObjectName("titleMarkBar")
        self.setMovable(False)
        self.setFloatable(False)
        toggle = self.toggleViewAction()
        if toggle is not None:
            toggle.setVisible(False)  # keep it out of the toolbar context menu
        self.addWidget(_spacer(self))
        self.addWidget(MarkLabel(self, MERGED_MARK_HEIGHT if merged else MARK_HEIGHT))
        self.addWidget(_spacer(self))
        if merged:
            self.setFixedHeight(TITLE_BAR_HEIGHT)
            self.setContentsMargins(0, 0, 0, 0)

    def mousePressEvent(self, a0: QMouseEvent | None) -> None:
        handle = self._window.windowHandle()
        if (
            self.merged
            and a0 is not None
            and a0.button() == Qt.MouseButton.LeftButton
            and handle is not None
            and handle.startSystemMove()
        ):
            return
        super().mousePressEvent(a0)

    def mouseDoubleClickEvent(self, a0: QMouseEvent | None) -> None:
        window = self._window
        if not self.merged:
            super().mouseDoubleClickEvent(a0)
        elif window.isMaximized():
            window.showNormal()
        else:
            window.showMaximized()


def addTitleMarkBar(
    window: QMainWindow, mergeWithTitleBar: bool = sys.platform == "darwin"
) -> TitleMarkBar:
    """Add the fixed V-mark bar, centred like a title, to the top of ``window``.
    Call before the window is first shown."""
    bar = TitleMarkBar(window, merged=mergeWithTitleBar)
    window.addToolBar(Qt.ToolBarArea.TopToolBarArea, bar)
    if mergeWithTitleBar:
        window.setWindowFlag(Qt.WindowType.MaximizeUsingFullscreenGeometryHint, True)
        window.setWindowFlag(Qt.WindowType.NoTitleBarBackgroundHint, True)
        # Lay out from the very top instead of below the title bar
        window.setAttribute(
            Qt.WidgetAttribute.WA_ContentsMarginsRespectsSafeArea, False
        )
        window.setAccessibleName(window.windowTitle())
        window.setWindowTitle("")
    return bar


def _spacer(parent: QWidget) -> QWidget:
    spacer = QWidget(parent)
    spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    return spacer
