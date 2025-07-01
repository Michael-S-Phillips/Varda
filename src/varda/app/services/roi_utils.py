# src/varda/app/services/roi_service.py
import logging

import numpy as np
from typing import List, Tuple, Any
from numpy.typing import ArrayLike
from matplotlib.path import Path
import pyqtgraph as pg
from PyQt6.QtCore import QPointF, QRectF
from PyQt6.QtGui import QPolygonF, QPainterPath

import varda
from varda.app.services import image_utils
from varda.core.entities import ROI, Image
from varda.core.entities import ROIMode

logger = logging.getLogger(__name__)


class VardaROI(pg.ROI):
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
        self._setPenAndBrush()
        self.poly: QPolygonF = QPolygonF()

        super().__init__(pos=pos, size=size, pen=self.currentPen, **kwargs)
        self.calculatePolygon()

    def refresh(self):
        """Refresh the ROI item to update its appearance"""
        self._setPenAndBrush()
        self.calculatePolygon()
        self.update()

    def _setPenAndBrush(self):
        """Set the pen and brush for the ROI based on the entity color"""
        color = self.roiEntity.color
        self.currentPen = pg.mkPen(color=(color[0], color[1], color[2]), width=2)
        self.currentBrush = pg.mkBrush(self.roiEntity.color)

    def setROIData(self, roiEntity: ROI):
        """Set the ROI data from an existing ROI entity"""
        self.roiEntity = roiEntity
        self.refresh()

    def calculatePolygon(self):
        """Calculate the polygon from the ROI points"""
        # Create a QPolygonF from the ROI points
        polygon = QPolygonF()

        points = self.roiEntity.points
        if len(points) > 0:
            for point in points:
                # convert points from absolute to normalized [0-1] coordinates
                normalizedPoint = self._absToNormalizedPoint(point)
                polygon.append(normalizedPoint)
            if len(polygon) >= 3:
                polygon.append(polygon[0])  # Close the polygon
        self.poly = polygon

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

    def getArrayRegion(
        self, data, img, axes=(0, 1), returnMappedCoords=False, **kwargs
    ):
        """get the array region within the bounds of the ROI. see pg.ROI.getArrayRegion() for arg descriptions."""
        if not self.poly.isClosed():
            # this probably should never happen
            exc = ValueError("ROI polygon is not closed. Cannot get array region.")
            logger.error(exc)
            raise exc

        return self._getArrayRegionForArbitraryShape(
            data, img, axes, returnMappedCoords, **kwargs
        )

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
    def getROI(roiEntity: ROI, **kwargs) -> "VardaROI":
        """
        Factory method to create a VardaROI from an existing ROI entity.

        Args:
            roiEntity: The ROI entity to create the VardaROI from.
            **kwargs: Additional parameters for the VardaROI.

        Returns:
            VardaROI: The created VardaROI instance.
        """
        return VardaROI(roiEntity, movable=False, **kwargs)

    @staticmethod
    def rectROI(
        position: Tuple[float, float],
        size: Tuple[float, float],
        sourceImageIndex: int,
        color: Tuple[int, int, int, int] | Tuple[int, int, int],
        **kwargs,
    ) -> "VardaROI":
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
        roi = VardaROI(entity, **kwargs)
        # Add scale handle for resizing rect.
        roi.addScaleHandle([1, 1], [0, 0])
        return roi


class RegionCoordinateTransform:
    """
    Handles 2D coordinate transformations between local ROI space and global image space. using affine transformations.
    Note that the methods accept x, y coordinates, since that's the most convenient.
    but internally the calculations are done in row, col order by swapping the axes.
    """

    def __init__(self, origin, basisVectors):
        """
        Initialize the transform with origin and basis vectors.

        Args:
            origin: (row, col) array defining the origin in global coordinates
            basisVectors: Two (row, col) arrays defining the basis vectors in global coordinates
        """
        self.origin = np.asarray(origin)
        self.vx, self.vy = map(np.asarray, basisVectors)

    def localToGlobal(self, coords) -> np.ndarray:
        """
        convert a set of local coordinates to global coordinates.

        Args:
            coords: (..., (x, y)) array of local coordinates to convert.
        Returns:
            (..., (x, y)) array of global coordinates
        """
        coords = np.asarray(coords)

        # convert (..., (x, y)) to (..., (row, col))
        col = coords[..., 0]
        row = coords[..., 1]

        # compute in (row, col) space
        rc = self.origin + row[..., None] * self.vx + col[..., None] * self.vy
        # rc[...,0] is row, rc[...,1] is col

        # return as (x, y) = (col, row)
        return np.stack([rc[..., 1], rc[..., 0]], axis=-1)

    def globalToLocal(self, coords) -> np.ndarray:
        """
        convert a set of global coordinates to local coordinates.

        Args:
            coords: (..., (x, y)) array of global coordinates to convert
        Returns:
            (..., (x, y)) array of local coordinates
        """
        coords = np.asarray(coords)
        # convert (..., (x, y)) to (..., (row, col))
        col = coords[..., 0]
        row = coords[..., 1]
        rc = np.stack([row, col], axis=-1)

        # subtract origin in (row, col)
        delta = rc - self.origin

        # solve M @ [r; c] = delta for [r, c]
        M = np.column_stack((self.vx, self.vy))  # shape (2,2)
        local_rc = np.linalg.solve(M, delta.T).T  # gives (row, col)

        # swap back to (x, y) = (col, row)
        return np.stack([local_rc[..., 1], local_rc[..., 0]], axis=-1)


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


def createROIMask(points: np.ndarray, shape: Tuple[int, int]) -> np.ndarray:
    """
    Create a binary mask from ROI points

    Args:
        points: Nx2 array of (x, y) aka (row, col) coordinates defining the ROI polygon
        shape: (height, width) of the output mask
    """

    # create a matplotlib path from the points
    path = Path(points)

    # Create a grid of all image coordinates
    y, x = np.mgrid[: shape[0], : shape[1]]
    coords = np.column_stack((x.ravel(), y.ravel()))

    # Test which points are inside the path
    mask = path.contains_points(coords).reshape(shape)

    return mask


def getMaskedArrayRegionSimple(
    roi: ROI, image: Image | np.ndarray, order=1, returnTransform=False
) -> Tuple[np.ndarray, RegionCoordinateTransform] | np.ndarray:
    """
    Uses the axis-aligned bounding box of the ROI to extract an array region, and applies a mask based on the ROI shape.

    Args:
        roi: The ROI entity
        image: The image entity
        order: the type of resampling. 0 = nearest neighbor, 1 = bilinear, 2 = cubic, etc.
        returnTransform: If True, also return a RegionCoordinateTransform object for mapping coordinates
    Returns:
        The masked array region, and optionally the coordinate transform
    """
    # get image data
    if isinstance(image, Image):
        data = image.raster
    elif isinstance(image, np.ndarray):
        data = image
    else:
        raise TypeError("image input must be an Image entity or a numpy ndarray.")

    # Bounding box of the polygon
    min_x, min_y, max_x, max_y = roi.getBoundingBox()

    # validate that the bounding box is within the image
    if min_x < 0 or min_y < 0 or max_x > data.shape[1] or max_y > data.shape[0]:
        raise ValueError(
            f"ROI bounding box {min_x, min_y, max_x, max_y} is out of image bounds {data.shape[1], data.shape[0]}"
        )

    width = int(np.ceil(max_x - min_x))
    height = int(np.ceil(max_y - min_y))

    # Extract a rectangular slice of the data.
    shape = (height, width)
    origin = (min_y, min_x)
    vectors = ((1.0, 0.0), (0.0, 1.0))
    arraySlice = pg.affineSlice(data, shape, origin, vectors, axes=(0, 1), order=order)

    # Mask out only the polygon region
    localPoints = roi.points - np.array([min_x, min_y])
    mask = createROIMask(localPoints, (height, width))
    # np.newaxis is to explicitly give the mask the same number of dimensions as arraySlice. For some reason need to do that.
    maskedArray = np.where(mask[..., np.newaxis], arraySlice, np.nan)

    if returnTransform:
        transform = RegionCoordinateTransform(origin=origin, basisVectors=vectors)
        return maskedArray, transform

    return maskedArray


def getMaskedArrayRegionAffine(roi: ROI, image: Image) -> np.ndarray:
    """
    The purpose of this function would be to support more complex affine slices. But idk if we even need that?
    """
    raise NotImplementedError("Affine ROI extraction not implemented yet.")


def _evaluateFormula(formula: str, roi: ROI, imageIndices) -> Any:
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
        "num_images": len(imageIndices),
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
