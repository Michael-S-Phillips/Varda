# src/varda/app/services/roi_service.py
import logging
import uuid
import numpy as np
from typing import List, Tuple, Dict, Optional, Any

import pyqtgraph as pg
from PyQt6 import QtCore, QtGui

import varda
from varda.app.services import image_utils
from varda.core.entities import ROI
from varda.core.entities import ROIMode

logger = logging.getLogger(__name__)


def createROI(
    points: List[Tuple[float, float]],
    sourceImageIndex: int,
    color: Tuple[int, int, int, int],
    mode: ROIMode,
) -> ROI:
    """Create a new ROI and save it to the project"""
    kwargs = {
        "points": np.array(points),
        "sourceImageIndex": sourceImageIndex,
        "color": color,
        "mode": mode,
    }

    # Calculate geo coordinates if available
    image = varda.app.proj.getImage(sourceImageIndex)
    if image.metadata.hasGeospatialData:
        geoPoints = [image_utils.transformPixelToGeoCoord(image, *p) for p in points]
        geoPoints = np.array(geoPoints)
        kwargs["geoPoints"] = geoPoints

    # Create ROI object
    roi = ROI(**kwargs)

    # Save to project
    varda.app.proj.roiManager.addROI(roi)
    varda.app.proj.roiManager.associateROIWithImage(roi, sourceImageIndex)
    return roi


def createROIMask(
    points: List[Tuple[float, float]], shape: Tuple[int, int]
) -> np.ndarray:
    """Create a binary mask from ROI points"""
    from matplotlib.path import Path

    # Convert points to the format Path expects
    path_points = np.array(points)

    # Create path
    path = Path(path_points)

    # Create a grid of all image coordinates
    y, x = np.mgrid[: shape[0], : shape[1]]
    coords = np.column_stack((x.ravel(), y.ravel()))

    # Test which points are inside the path
    mask = path.contains_points(coords).reshape(shape)
    return mask


def _evaluateFormula(formula: str, roi: ROI) -> Any:
    """
    Evaluate a formula for an ROI

    Args:
        formula: The formula to evaluate
        roi: The ROI to evaluate the formula for

    Returns:
        The result of the formula
    """
    # This is a simplified formula evaluator
    # A real implementation would need a proper formula parser

    # Create a safe environment with ROI properties
    env = {
        "roi": roi,
        "name": roi.name,
        "points": len(roi.points),
        "color": roi.color,
        "num_images": len(roi.image_indices),
    }

    # Add custom data
    for key, value in roi.customData.values.items():
        if isinstance(key, str) and key.isidentifier():
            env[key] = value

    # Add numpy functions
    env.update(
        {
            "np": np,
            "mean": np.mean,
            "sum": np.sum,
            "min": np.min,
            "max": np.max,
        }
    )

    # Basic formula evaluation
    # Note: eval() is generally not safe for user input, but this is just a placeholder
    # A real implementation would use a proper expression parser
    try:
        result = eval(formula, {"__builtins__": {}}, env)
        return result
    except Exception as e:
        logger.error(f"Error evaluating formula '{formula}': {e}")
        return None


class VardaROI(pg.ROI):
    """
    ROI class for drawing freehand polygons in pyqtgraph.
    Uses pyqtgraph's base ROI class for logic drawing and extracting array regions etc. But compatible with Varda's ROI entity.
    """

    def __init__(self, roiEntity: ROI, **kwargs):
        """
        Initialize VardaROI from entity data or standard ROI parameters

        Args:
            entity: ROI entity to initialize from
            **kwargs: Standard pyqtgraph ROI parameters
        """
        super().__init__(pen=roiEntity.color, **kwargs)
        self.roiEntity = roiEntity

        self.poly = QtGui.QPolygonF()

        self.calculatePolygon()

    def setROIData(self, roiEntity: ROI):
        """Set the ROI data from an existing ROI entity"""
        self.roiEntity = roiEntity
        self.calculatePolygon()
        self.update()

    def calculatePolygon(self):
        """Calculate the polygon from the ROI points"""
        # Create a QPolygonF from the ROI points
        polygon = QtGui.QPolygonF()
        points = self.roiEntity.points
        for point in points:
            polygon.append(QtCore.QPointF(*point))

        # Store the polygon for later use
        self.poly = polygon

    def shape(self):
        """This defines the shape of the ROI. Is used when getting array regions."""
        p = QtGui.QPainterPath()
        p.addPolygon(self.poly)
        return p

    def paint(self, p, opt, widget):
        """This defines how the ROI is drawn."""
        self.currentPen = pg.mkPen(*self.roiEntity.color)
        self.currentBrush = pg.mkBrush(
            *self.roiEntity.color, alpha=self.roiEntity.fillOpacity
        )
        p.setPen(self.currentPen)
        p.setBrush(self.currentBrush)
        p.drawPolygon(self.poly)

    def boundingRect(self):
        """Return the bounding rectangle of the ROI."""
        return self.shape().boundingRect()

    def getArrayRegion(
        self, data, img, axes=(0, 1), returnMappedCoords=False, **kwargs
    ):
        """get the array region within the bounds of the ROI. see pg.ROI.getArrayRegion() for arg descriptions."""
        return self._getArrayRegionForArbitraryShape(
            data, img, axes, returnMappedCoords, **kwargs
        )
