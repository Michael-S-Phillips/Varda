"""
High level classes and utility functions for working with ROIs in Varda.
TODO: We could split this up into more specific categories each with their own file, if needed.
"""

import logging

import numpy as np
from typing import List, Tuple, Any, Dict
from numpy.typing import ArrayLike
import pyqtgraph as pg
from PyQt6.QtCore import QPointF, QRectF
from PyQt6.QtGui import QPolygonF, QPainterPath, QColor
from scipy import stats

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
        self.currentPen = pg.mkPen(color=color, width=2)
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
        color: QColor,
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


class ROIStatistics:
    """Class to calculate and store statistics based on an ROI and an image."""

    def __init__(self, roi: ROI, image: Image):
        """
        Initialize with the data array from within an ROI.

        Args:
            maskedData: Numpy array containing the spectral data within the ROI.
                      Shape should be (n_pixels, n_bands) or (n_pixels, y, x, n_bands)
        """

        # mask out the region
        imageData = image.raster
        mask = createROIMaskAlternative(roi.points, imageData.shape[:2])
        maskedData = imageData[mask]

        # Ensure data is in the right shape
        if maskedData.ndim > 2:
            # Flatten spatial dimensions
            self.data = maskedData.reshape(-1, maskedData.shape[-1])
        else:
            self.data = maskedData

        self.n_pixels = self.data.shape[0]
        self.n_bands = self.data.shape[1]

        # Calculate basic statistics
        self._calculateBasicStats()

    def _calculateBasicStats(self):
        """Calculate basic statistics for the ROI data."""
        # Skip NaN values in calculations
        self.mean = np.nanmean(self.data, axis=0)
        self.median = np.nanmedian(self.data, axis=0)
        self.std = np.nanstd(self.data, axis=0)
        self.min = np.nanmin(self.data, axis=0)
        self.max = np.nanmax(self.data, axis=0)
        self.percentile_25 = np.nanpercentile(self.data, 25, axis=0)
        self.percentile_75 = np.nanpercentile(self.data, 75, axis=0)

        # Count valid (non-NaN) pixels per band
        self.valid_pixel_count = np.sum(~np.isnan(self.data), axis=0)

        # Calculate additional statistics
        self._calculateAdvancedStats()

    def _calculateAdvancedStats(self):
        """Calculate more advanced statistics."""
        # Coefficient of variation
        self.cv = np.zeros_like(self.mean)
        nonzero_mean = self.mean != 0
        self.cv[nonzero_mean] = self.std[nonzero_mean] / self.mean[nonzero_mean]

        # Skewness and kurtosis
        self.skewness = np.zeros(self.n_bands)
        self.kurtosis = np.zeros(self.n_bands)

        for i in range(self.n_bands):
            valid_data = self.data[:, i][~np.isnan(self.data[:, i])]
            if len(valid_data) > 2:  # Need at least 3 points for skewness
                self.skewness[i] = stats.skew(valid_data)
                self.kurtosis[i] = stats.kurtosis(valid_data)

        # Calculate spectral indices if we have enough bands
        if self.n_bands >= 3:
            self._calculateSpectralIndices()

    def _calculateSpectralIndices(self):
        """Calculate common spectral indices if appropriate bands exist."""
        # This would be expanded based on the specific bands available
        # For now, just placeholders
        self.spectral_indices = {}

        # If we knew which bands correspond to red, nir, etc.
        # we could calculate indices like NDVI
        # Example (assuming band order is known):
        # red_band = 2
        # nir_band = 3
        # self.spectral_indices['NDVI'] = (self.mean[nir_band] - self.mean[red_band]) /
        #                                 (self.mean[nir_band] + self.mean[red_band])

    def getSummary(self) -> Dict[str, Any]:
        """
        Get a summary of the ROI statistics.

        Returns:
            Dict with statistics summary
        """
        return {
            "n_pixels": self.n_pixels,
            "n_bands": self.n_bands,
            "valid_pixels": self.valid_pixel_count.tolist(),
            "mean": self.mean.tolist(),
            "median": self.median.tolist(),
            "std_dev": self.std.tolist(),
            "min": self.min.tolist(),
            "max": self.max.tolist(),
            "percentile_25": self.percentile_25.tolist(),
            "percentile_75": self.percentile_75.tolist(),
            "coefficient_of_variation": self.cv.tolist(),
            "skewness": self.skewness.tolist(),
            "kurtosis": self.kurtosis.tolist(),
            "spectral_indices": self.spectral_indices,
        }

    def getBandStats(self, band_idx: int) -> Dict[str, Any]:
        """
        Get statistics for a specific band.

        Args:
            band_idx: Index of the band

        Returns:
            Dict with statistics for the specified band
        """
        if band_idx < 0 or band_idx >= self.n_bands:
            raise ValueError(f"Band index {band_idx} out of range (0-{self.n_bands-1})")

        return {
            "mean": float(self.mean[band_idx]),
            "median": float(self.median[band_idx]),
            "std_dev": float(self.std[band_idx]),
            "min": float(self.min[band_idx]),
            "max": float(self.max[band_idx]),
            "percentile_25": float(self.percentile_25[band_idx]),
            "percentile_75": float(self.percentile_75[band_idx]),
            "coefficient_of_variation": float(self.cv[band_idx]),
            "skewness": float(self.skewness[band_idx]),
            "kurtosis": float(self.kurtosis[band_idx]),
            "valid_pixels": int(self.valid_pixel_count[band_idx]),
        }

    def compareBands(self, band1_idx: int, band2_idx: int) -> Dict[str, Any]:
        """
        Compare statistics between two bands.

        Args:
            band1_idx: Index of the first band
            band2_idx: Index of the second band

        Returns:
            Dict with comparison results
        """
        if (
            band1_idx < 0
            or band1_idx >= self.n_bands
            or band2_idx < 0
            or band2_idx >= self.n_bands
        ):
            raise ValueError(f"Band indices out of range (0-{self.n_bands-1})")

        # Get valid data for both bands
        valid_mask = ~np.isnan(self.data[:, band1_idx]) & ~np.isnan(
            self.data[:, band2_idx]
        )
        band1_data = self.data[valid_mask, band1_idx]
        band2_data = self.data[valid_mask, band2_idx]

        # Skip if not enough data points
        if len(band1_data) < 2:
            return {"error": "Not enough valid data points for comparison"}

        # Calculate correlation
        correlation, p_value = stats.pearsonr(band1_data, band2_data)

        # Calculate band ratio
        mean_ratio = np.mean(band1_data / np.where(band2_data == 0, np.nan, band2_data))

        return {
            "correlation": float(correlation),
            "p_value": float(p_value),
            "mean_ratio": float(mean_ratio),
            "mean_difference": float(np.mean(band1_data - band2_data)),
            "valid_pixels": int(np.sum(valid_mask)),
        }

    def histogram(self, band_idx: int, bins: int = 50) -> Tuple[np.ndarray, np.ndarray]:
        """
        Calculate histogram for a specific band.

        Args:
            band_idx: Index of the band
            bins: Number of bins for the histogram

        Returns:
            Tuple of (bin_centers, histogram_values)
        """
        if band_idx < 0 or band_idx >= self.n_bands:
            raise ValueError(f"Band index {band_idx} out of range (0-{self.n_bands-1})")

        band_data = self.data[:, band_idx]
        valid_data = band_data[~np.isnan(band_data)]

        hist, bin_edges = np.histogram(valid_data, bins=bins)
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

        return bin_centers, hist

    @staticmethod
    def compareROIs(roi_stats1, roi_stats2):
        """
        Compare statistics between two ROIs.

        Args:
            roi_stats1: First ROIStatistics object
            roi_stats2: Second ROIStatistics object

        Returns:
            Dict with comparison results
        """
        if roi_stats1.n_bands != roi_stats2.n_bands:
            return {"error": "ROIs have different number of bands"}

        # Calculate differences between means
        mean_diff = roi_stats1.mean - roi_stats2.mean
        mean_diff_percent = (
            mean_diff / np.where(roi_stats2.mean == 0, np.nan, roi_stats2.mean) * 100
        )

        # Calculate spectral angle mapper (SAM)
        norm1 = np.linalg.norm(roi_stats1.mean)
        norm2 = np.linalg.norm(roi_stats2.mean)
        dot_product = np.sum(roi_stats1.mean * roi_stats2.mean)
        sam = np.arccos(dot_product / (norm1 * norm2))

        # Calculate Euclidean distance
        euclidean_dist = np.linalg.norm(roi_stats1.mean - roi_stats2.mean)

        return {
            "mean_difference": mean_diff.tolist(),
            "mean_difference_percent": mean_diff_percent.tolist(),
            "spectral_angle": float(sam),
            "euclidean_distance": float(euclidean_dist),
            "roi1_pixels": roi_stats1.n_pixels,
            "roi2_pixels": roi_stats2.n_pixels,
        }

    @staticmethod
    def getROIStats(roi: ROI, image: Image):
        """
        Calculate statistics for an ROI from image data.

        Args:
            roi: The ROI object (containing points or mask)
            image: The full image data array

        Returns:
            ROIStatistics object
        """
        # Extract data for the ROI
        if len(roi.points) == 0:
            logger.error("ROI has no points defined")
            return None

        # TODO: this logic checking that an ROI is valid could be moved to some central utility function
        xMin, yMin, xMax, yMax = roi.getBounds()
        if xMin < 0 or yMin < 0 or xMax > image.width or yMax > image.height:
            logger.error("ROI is out of image bounds")
            return None

        return ROIStatistics(roi, image)


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
    from matplotlib.path import Path

    # create a matplotlib path from the points
    path = Path(points)

    # Create a grid of all image coordinates
    y, x = np.mgrid[: shape[0], : shape[1]]
    coords = np.column_stack(
        (x.ravel() + 0.5, y.ravel() + 0.5)
    )  # +0.5 for pixel center

    # Test which points are inside the path
    mask = path.contains_points(coords).reshape(shape)

    return mask


def createROIMaskAlternative(points: np.ndarray, shape: Tuple[int, int]):
    """
    Create a binary mask from ROI points. But uses skimage polygon instead of matplotlib Path. Idk which is better

    Args:
        points: List of points defining the ROI
        shape: Shape of the image (height, width)

    Returns:
        Binary mask array
    """
    from skimage.draw import polygon

    x_coords = [p[0] for p in points]
    y_coords = [p[1] for p in points]

    # Create mask
    mask = np.zeros(shape, dtype=bool)
    rr, cc = polygon(y_coords, x_coords, shape)
    mask[rr, cc] = True

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
    min_x, min_y, max_x, max_y = roi.getBounds()

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
    arraySlice = pg.affineSlice(
        data, shape, origin, vectors, axes=(0, 1), order=order, default=np.nan
    )

    # Mask out only the polygon region
    localPoints = roi.points - np.array([min_x, min_y])
    mask = createROIMask(localPoints, (height, width))
    mask = np.broadcast_to(~mask[..., np.newaxis], arraySlice.shape)
    maskedArray = np.ma.masked_array(arraySlice, mask=mask)
    # np.newaxis is to explicitly give the mask the same number of dimensions as arraySlice. For some reason need to do that.
    # maskedArray = np.where(mask[..., np.newaxis], arraySlice, np.nan)

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
