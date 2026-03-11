"""New simplified ROI graphics item for display on viewports."""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import QPointF, QRectF
from PyQt6.QtGui import QPainter, QPainterPath, QPolygonF, QColor, QPen, QBrush

from varda.common.entities import VardaROI


class VardaROIGraphicsItem(pg.GraphicsObject):
    """A simple polygon graphics item for displaying an ROI on a viewport.

    Unlike the old ``VardaROIItem`` (which extended ``pg.ROI`` with move/resize
    handles), this item is display-only. The controller handles coordinate
    conversion and passes pre-computed pixel coordinates.

    Args:
        roi: Immutable VardaROI snapshot.
        pixelCoords: Nx2 array of (col, row) pixel coordinates.
    """

    def __init__(self, roi: VardaROI, pixelCoords: np.ndarray) -> None:
        super().__init__()
        self._roi = roi
        self._pixelCoords = pixelCoords
        self._isHighlighted = False
        self._polygon = QPolygonF()
        self._pen = QPen()
        self._brush = QBrush()

        self._buildPolygon()
        self._updateStyle()

    @property
    def roi(self) -> VardaROI:
        return self._roi

    @property
    def fid(self) -> int:
        return self._roi.fid

    def updateData(self, roi: VardaROI, pixelCoords: np.ndarray) -> None:
        """Update the displayed ROI data and re-render."""
        self.prepareGeometryChange()
        self._roi = roi
        self._pixelCoords = pixelCoords
        self._buildPolygon()
        self._updateStyle()
        self.update()

    def setHighlighted(self, highlighted: bool) -> None:
        if self._isHighlighted != highlighted:
            self._isHighlighted = highlighted
            self._updateStyle()
            self.update()

    def boundingRect(self) -> QRectF:
        return self._polygon.boundingRect()

    def shape(self) -> QPainterPath:
        p = QPainterPath()
        p.addPolygon(self._polygon)
        return p

    def paint(self, p: QPainter, opt, widget) -> None:
        p.setPen(self._pen)
        p.setBrush(self._brush)
        p.drawPolygon(self._polygon)

    def _buildPolygon(self) -> None:
        self._polygon = QPolygonF()
        for col, row in self._pixelCoords:
            self._polygon.append(QPointF(col, row))
        if len(self._pixelCoords) >= 3:
            self._polygon.append(QPointF(*self._pixelCoords[0]))

    def _updateStyle(self) -> None:
        r, g, b, a = self._roi.color
        if self._isHighlighted:
            color = QColor(255, 255, 0, a)
        else:
            color = QColor(r, g, b, a)
        self._pen = pg.mkPen(color=(color.red(), color.green(), color.blue()), width=2)
        self._brush = pg.mkBrush(color)
