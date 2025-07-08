import logging
from typing import Tuple, Optional

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QPolygonF, QPainterPath, QColor

from varda.app.services.roi_utils import RegionCoordinateTransform
from varda.core.entities import ROI, ROIMode

logger = logging.getLogger(__name__)


class VardaROIItem(pg.ROI):
    """
    Frontend ROI class for drawing ROIs. Supports arbitrary polygon shapes.
    Uses pyqtgraph's base ROI class for logic drawing and extracting array regions etc. But compatible with Varda's ROI entity.
    """

    def __init__(self, roiEntity: ROI, **kwargs):
        """
        Initialize VardaROI from entity data or standard ROI parameters

        Args:
            entity: ROI entity to initialize from
            **kwargs: Standard pyqtgraph ROI parameters
        """
        points = roiEntity.points
        # calculate position and size based on points
        if len(points) > 0:
            xCoords = [p[0] for p in points]
            yCoords = [p[1] for p in points]
            xMin, xMax = min(xCoords), max(xCoords)
            yMin, yMax = min(yCoords), max(yCoords)
            pos = [xMin, yMin]
            size = [xMax - xMin, yMax - yMin]
        else:
            pos = [0, 0]
            size = [1, 1]
        self.roiEntity = roiEntity
        self.coordTransform: Optional[RegionCoordinateTransform] = None
        self.poly: QPolygonF = QPolygonF()
        self.isHighlighted = False
        super().__init__(pos=pos, size=size, **kwargs)

        self._setPenAndBrush()
        self.calculatePolygon()

    def refresh(self):
        """Refresh the ROI item to update its appearance"""
        self.prepareGeometryChange()
        self._setPenAndBrush()
        self.calculatePolygon()
        self.update()

    def _setPenAndBrush(self):
        """Set the pen and brush for the ROI based on the entity color"""
        if self.isHighlighted:
            color = QColor(255, 255, 0, self.roiEntity.color.alpha())
        else:
            color = self.roiEntity.color

        self.currentPen = pg.mkPen(
            color=(color.red(), color.green(), color.blue()), width=2
        )
        self.currentBrush = pg.mkBrush(color)

    def setROIData(self, roiEntity: ROI):
        """Set the ROI data from an existing ROI entity"""
        self.roiEntity = roiEntity
        self.refresh()

    def setCoordinateTransform(self, transform: RegionCoordinateTransform):
        self.coordTransform = transform
        self.refresh()

    def setHighlighted(self, highlighted: bool):
        """Highlight the ROI by changing its pen and brush"""
        self.isHighlighted = highlighted
        self.refresh()

    def calculatePolygon(self):
        """Calculate the polygon from the ROI points"""
        # Create a QPolygonF from the ROI points
        self.poly = QPolygonF()

        points = self.roiEntity.points
        if len(points) == 0:
            return

        if self.coordTransform is not None:
            # transform points according to the coordinate transform
            points = self.coordTransform.globalToLocal(points)

        for point in points:
            # convert points from absolute to normalized [0-1] coordinates
            normalizedPoint = self._absToNormalizedPoint(point)
            self.poly.append(normalizedPoint)
        if len(self.poly) >= 3:
            self.poly.append(self.poly[0])  # Close the polygon

    def shape(self):
        """This defines the shape of the ROI. Is used when getting array regions."""
        p = QPainterPath()
        scaledPoly = QPolygonF()
        size = self.size()
        for point in self.poly:
            scaledPoint = QPointF(point.x() * size.x(), point.y() * size.y())
            scaledPoly.append(scaledPoint)
        p.addPolygon(scaledPoly)
        return p

    def paint(self, p, opt, widget):
        """This defines how the ROI is drawn."""
        p.setPen(self.currentPen)
        p.setBrush(self.currentBrush)

        # Scale polygon to current ROI size for drawing
        scaledPoly = QPolygonF()
        size = self.size()
        for point in self.poly:
            scaledPoint = QPointF(point.x() * size[0], point.y() * size[1])
            scaledPoly.append(scaledPoint)

        p.drawPolygon(scaledPoly)

    def stateChanged(self, finish=True):
        """Called when ROI state changes (position, size, etc.)"""
        super().stateChanged(finish)
        # Update the entity's points when the ROI is moved/scaled
        self.updateEntityPoints()

    def updateEntityPoints(self):
        """Update the entity's points based on current ROI state"""
        # Convert relative polygon points back to absolute coordinates
        pos = self.pos()
        size = self.size()
        newPoints = []

        # Skip the last point if it's a duplicate of the first (closing point)
        pointsToConvert = (
            self.poly[:-1]
            if len(self.poly) > 0 and self.poly[0] == self.poly[-1]
            else self.poly
        )

        for point in pointsToConvert:
            newPoints.append(self._normalizedToAbsPoint(point))

        if newPoints:
            self.roiEntity.points = np.array(newPoints)

    def boundingRect(self):
        """Return the bounding rectangle of the ROI."""
        return self.shape().boundingRect()

    # TODO: Probably delete this but I'll wait until I'm positive we don't need it.
    #  use roi_utils.getMaskedArrayRegionSimple() to get array regions instead.
    # def getArrayRegion(
    #     self, data, img, axes=(0, 1), returnMappedCoords=False, **kwargs
    # ):
    #     """get the array region within the bounds of the ROI. see pg.ROI.getArrayRegion() for arg descriptions."""
    #     if not self.poly.isClosed():
    #         # this probably should never happen
    #         exc = ValueError("ROI polygon is not closed. Cannot get array region.")
    #         logger.error(exc)
    #         raise exc
    #
    #     return self._getArrayRegionForArbitraryShape(
    #         data, img, axes, returnMappedCoords, **kwargs
    #     )

    def _absToNormalizedPoint(self, point: Tuple[float, float]) -> QPointF:
        """Get the normalized point of the ROI."""
        pos = self.pos()
        size = self.size()
        normX = (point[0] - pos.x()) / size.x() if size.x() != 0 else 0
        normY = (point[1] - pos.y()) / size.y() if size.y() != 0 else 0
        return QPointF(normX, normY)

    def _normalizedToAbsPoint(self, point: QPointF) -> Tuple[float, float]:
        """Convert a normalized point to absolute coordinates."""
        pos = self.pos()
        size = self.size()
        absX = pos.x() + point.x() * size.x()
        absY = pos.y() + point.y() * size.y()
        return absX, absY

    @staticmethod
    def getROI(roiEntity: ROI, **kwargs) -> "VardaROIItem":
        """
        Factory method to create a VardaROI from an existing ROI entity.

        Args:
            roiEntity: The ROI entity to create the VardaROI from.
            **kwargs: Additional parameters for the VardaROI.

        Returns:
            VardaROIItem: The created VardaROI instance.
        """
        return VardaROIItem(roiEntity, **kwargs)

    @staticmethod
    def rectROI(
        position: Tuple[float, float],
        size: Tuple[float, float],
        sourceImageIndex: int,
        color: QColor,
        **kwargs,
    ) -> "VardaROIItem":
        """Factory method to create a rectangular VardaROI."""
        x, y = position
        w, h = size
        points = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
        entity = ROI(
            points=np.array(points),
            sourceImageIndex=sourceImageIndex,
            color=color,
            mode=ROIMode.RECTANGLE,
        )
        roi = VardaROIItem(entity, **kwargs)
        # Add scale handle for resizing rect.
        roi.addScaleHandle([1, 1], [0, 0])
        return roi
