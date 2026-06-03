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
from PyQt6.QtCore import QPointF, QRectF
from PyQt6.QtGui import QBrush, QColor, QPainterPath, QPen, QPolygonF
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


class PyqtgraphTextOverlay:
    """A `pg.TextItem` label positioned in view (data) coordinates."""

    def __init__(
        self,
        viewBox: pg.ViewBox,
        text: str,
        pos: QPointF,
        color: str,
        fontSize: int,
        backgroundColor: str,
        backgroundAlpha: int,
        anchor: tuple[float, float],
    ):
        self._item = pg.TextItem(text=text, color=color, anchor=anchor)
        font = self._item.textItem.font()
        font.setPointSize(fontSize)
        self._item.textItem.setFont(font)
        if backgroundColor:
            self._item.fill = pg.mkBrush(color=backgroundColor, alpha=backgroundAlpha)
            self._item.border = pg.mkPen(color=backgroundColor, width=1)
        self._item.setPos(pos)
        self._viewBox = viewBox
        viewBox.addItem(self._item, ignoreBounds=True)

    def setText(self, text: str) -> None:
        self._item.setText(text)

    def setPos(self, pos: QPointF) -> None:
        self._item.setPos(pos)

    def setVisible(self, visible: bool) -> None:
        self._item.setVisible(visible)

    def remove(self) -> None:
        self._viewBox.removeItem(self._item)


class PyqtgraphROIOverlay(pg.GraphicsObject):
    """A display-only ROI polygon: coloured outline + fill, with a highlight state.

    Points are in viewport-local coordinates. This is both the handle and the
    graphics item (a `pg.GraphicsObject`), so it can paint a closed, filled polygon
    while still satisfying the `ROIOverlayHandle` protocol.
    """

    _HIGHLIGHT = QColor(255, 255, 0)

    def __init__(self, viewBox: pg.ViewBox, points: Sequence[QPointF], color: QColor):
        super().__init__()
        self._color = color
        self._highlighted = False
        self._polygon = QPolygonF()
        self._pen = QPen()
        self._brush = QBrush()
        self._buildPolygon(points)
        self._updateStyle()
        # NB: not `_viewBox` — pg.GraphicsItem uses that name internally.
        self._hostViewBox = viewBox
        viewBox.addItem(self, ignoreBounds=True)

    def setPoints(self, points: Sequence[QPointF]) -> None:
        self.prepareGeometryChange()
        self._buildPolygon(points)
        self.update()

    def setColor(self, color: QColor) -> None:
        self._color = color
        self._updateStyle()
        self.update()

    def setHighlighted(self, highlighted: bool) -> None:
        if self._highlighted != highlighted:
            self._highlighted = highlighted
            self._updateStyle()
            self.update()

    def remove(self) -> None:
        self._hostViewBox.removeItem(self)

    def boundingRect(self) -> QRectF:
        return self._polygon.boundingRect()

    def shape(self) -> QPainterPath:
        path = QPainterPath()
        path.addPolygon(self._polygon)
        return path

    def paint(self, painter, option, widget=None) -> None:
        painter.setPen(self._pen)
        painter.setBrush(self._brush)
        painter.drawPolygon(self._polygon)

    def _buildPolygon(self, points: Sequence[QPointF]) -> None:
        pts = list(points)
        polygon = QPolygonF()
        for point in pts:
            polygon.append(point)
        if len(pts) >= 3:
            polygon.append(pts[0])  # close the polygon
        self._polygon = polygon

    def _updateStyle(self) -> None:
        color = self._color
        if self._highlighted:
            color = QColor(
                self._HIGHLIGHT.red(),
                self._HIGHLIGHT.green(),
                self._HIGHLIGHT.blue(),
                color.alpha(),
            )
        self._pen = pg.mkPen(color=(color.red(), color.green(), color.blue()), width=2)
        self._brush = pg.mkBrush(color)
