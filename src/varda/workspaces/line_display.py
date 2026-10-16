"""Keep a workspace's lines drawn on its viewport(s) in their colors, with
the selected lines highlighted, and mark where the pointer is on a profile."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

import numpy as np
from psygnal import SignalInstance
from PyQt6.QtCore import QObject, QPointF
from PyQt6.QtGui import QColor

from varda.image_rendering.raster_view.viewport_protocol import (
    PointOverlayHandle,
    PolylineOverlayHandle,
)
from varda.lines.line_collection import LineCollection

CURSOR_COLOR = QColor(255, 255, 255)


class LineViewport(Protocol):
    # Fires when the viewport's local coordinates move (it shows a region of
    # the image and was panned), so lines must be re-mapped.
    sigImageChanged: SignalInstance

    def pixelToLocalCoords(self, pixelCoords: np.ndarray) -> np.ndarray: ...

    def addPolylineOverlay(
        self, points: Sequence[QPointF], color: QColor, width: float = 2.0
    ) -> PolylineOverlayHandle: ...

    def addPointOverlay(
        self, pos: QPointF, color: QColor, symbol: str = "x"
    ) -> PointOverlayHandle: ...


def _points(viewport: LineViewport, vertices: np.ndarray) -> list[QPointF]:
    local = viewport.pixelToLocalCoords(np.asarray(vertices, dtype=float))
    return [QPointF(float(x), float(y)) for x, y in local]


class LineDisplay(QObject):
    def __init__(
        self,
        collection: LineCollection,
        viewports: Sequence[LineViewport],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._collection = collection
        self._viewports = list(viewports)
        self._handles: dict[int, list[PolylineOverlayHandle]] = {}
        self._highlighted: set[int] = set()
        self._cursor: np.ndarray | None = None  # image px
        self._cursorHandles: list[PointOverlayHandle] = []
        collection.sigCollectionChanged.connect(self.refresh)
        for viewport in self._viewports:
            viewport.sigImageChanged.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        for handles in self._handles.values():
            for handle in handles:
                handle.remove()
        self._handles.clear()
        for line in self._collection.lines():
            handles = []
            for viewport in self._viewports:
                handle = viewport.addPolylineOverlay(
                    _points(viewport, line.vertices), QColor(line.color)
                )
                handle.setHighlighted(line.fid in self._highlighted)
                handles.append(handle)
            self._handles[line.fid] = handles
        self._drawCursor()

    def highlight(self, fids: Sequence[int]) -> None:
        self._highlighted = set(fids)
        for fid, handles in self._handles.items():
            for handle in handles:
                handle.setHighlighted(fid in self._highlighted)

    def setCursor(self, position: np.ndarray | None) -> None:
        """Mark a point (image px) on every view, e.g. where the pointer is
        on a profile; None removes the mark."""
        self._cursor = None if position is None else np.asarray(position, float)
        self._drawCursor()

    def _drawCursor(self) -> None:
        for handle in self._cursorHandles:
            handle.remove()
        self._cursorHandles = []
        if self._cursor is None:
            return
        for viewport in self._viewports:
            (point,) = _points(viewport, self._cursor.reshape(1, 2))
            self._cursorHandles.append(
                viewport.addPointOverlay(point, CURSOR_COLOR, symbol="x")
            )
