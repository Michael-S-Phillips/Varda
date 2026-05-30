"""pyqtgraph-backed implementations of the viewport overlay handles.

These wrap concrete pyqtgraph / Qt graphics items and satisfy the backend-neutral
handle Protocols in `viewport_protocol`. They are the *only* place these specific
items are constructed; consumers receive a handle and never see the item, so a
future VisPy/pygfx viewport can return its own handles from the same factories.

Overlays are added to the viewport's `ViewBox` with ``ignoreBounds=True`` so they
never affect auto-range — the view stays framed on the image.
"""

from __future__ import annotations

from collections.abc import Sequence

import pyqtgraph as pg
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QBrush, QColor, QPen, QPolygonF
from PyQt6.QtWidgets import QGraphicsPolygonItem


class PyqtgraphCrosshair:
    """A vertical + horizontal `InfiniteLine` pair driven as one crosshair."""

    def __init__(self, viewBox: pg.ViewBox, color: QColor):
        pen = pg.mkPen(color)
        self._vLine = pg.InfiniteLine(angle=90, movable=False, pen=pen)
        self._hLine = pg.InfiniteLine(angle=0, movable=False, pen=pen)
        self._vLine.hide()
        self._hLine.hide()
        self._viewBox = viewBox
        viewBox.addItem(self._vLine, ignoreBounds=True)
        viewBox.addItem(self._hLine, ignoreBounds=True)

    def setPos(self, pos: QPointF) -> None:
        # InfiniteLine uses only the relevant axis of the point.
        self._vLine.setPos(pos)
        self._hLine.setPos(pos)

    def setVisible(self, visible: bool) -> None:
        self._vLine.setVisible(visible)
        self._hLine.setVisible(visible)

    def remove(self) -> None:
        self._viewBox.removeItem(self._vLine)
        self._viewBox.removeItem(self._hLine)


class PyqtgraphPolygonOverlay:
    """A filled `QGraphicsPolygonItem` whose points are in viewport-local coords."""

    def __init__(
        self,
        viewBox: pg.ViewBox,
        lineColor: QColor,
        fillColor: QColor,
        lineWidth: float,
    ):
        self._item = QGraphicsPolygonItem()
        self._item.setPen(QPen(lineColor, lineWidth))
        self._item.setBrush(QBrush(fillColor))
        self._viewBox = viewBox
        viewBox.addItem(self._item, ignoreBounds=True)

    def setPoints(self, points: Sequence[QPointF]) -> None:
        poly = QPolygonF()
        for p in points:
            poly.append(p)
        self._item.setPolygon(poly)

    def setVisible(self, visible: bool) -> None:
        self._item.setVisible(visible)

    def remove(self) -> None:
        self._viewBox.removeItem(self._item)
