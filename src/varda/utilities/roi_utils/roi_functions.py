from typing import List, Tuple, Any

import numpy as np
import pyqtgraph as pg

import varda
from varda.utilities import image_utils
from varda.utilities.roi_utils import RegionCoordinateTransform
from varda.common.entities import ROIMode, ROI, Image


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
    coords = np.column_stack((x.ravel() + 0.5, y.ravel() + 0.5))  # +0.5 for pixel center

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


def getRectImageRegion(
    roi: ROI, image: Image | np.ndarray, order=1, returnTransform=False
) -> Tuple[np.ndarray, RegionCoordinateTransform] | np.ndarray:
    """
    Uses the axis-aligned bounding box of the ROI to extract an array region.

    Args:
        roi: The ROI entity
        image: The image entity
        order: the type of resampling. 0 = nearest neighbor, 1 = bilinear, 2 = cubic, etc.
        returnTransform: If True, also return a RegionCoordinateTransform object for mapping coordinates
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
    if returnTransform:
        transform = RegionCoordinateTransform(origin=origin, basisVectors=vectors)
        return arraySlice, transform
    else:
        return arraySlice


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
    if returnTransform:
        arraySlice, transform = getRectImageRegion(roi, image, order, returnTransform)
    else:
        arraySlice = getRectImageRegion(roi, image, order, returnTransform)
        transform = None

    # # get image data
    # if isinstance(image, Image):
    #     data = image.raster
    # elif isinstance(image, np.ndarray):
    #     data = image
    # else:
    #     raise TypeError("image input must be an Image entity or a numpy ndarray.")
    #
    # # Bounding box of the polygon
    # min_x, min_y, max_x, max_y = roi.getBounds()
    #
    # # validate that the bounding box is within the image
    # if min_x < 0 or min_y < 0 or max_x > data.shape[1] or max_y > data.shape[0]:
    #     raise ValueError(
    #         f"ROI bounding box {min_x, min_y, max_x, max_y} is out of image bounds {data.shape[1], data.shape[0]}"
    #     )
    #
    # width = int(np.ceil(max_x - min_x))
    # height = int(np.ceil(max_y - min_y))
    #
    # # Extract a rectangular slice of the data.
    # shape = (height, width)
    # origin = (min_y, min_x)
    # vectors = ((1.0, 0.0), (0.0, 1.0))
    # arraySlice = pg.affineSlice(
    #     data, shape, origin, vectors, axes=(0, 1), order=order, default=np.nan
    # )

    # Mask out only the polygon region
    min_x, min_y, max_x, max_y = roi.getBounds()
    width = int(np.ceil(max_x - min_x))
    height = int(np.ceil(max_y - min_y))
    localPoints = roi.points - np.array([min_x, min_y])
    mask = createROIMask(localPoints, (height, width))
    mask = ~mask
    # reshape mask to match arraySlice dimensions, if necessary (sometimes arrayslice is 2d and sometimes 3d)
    if mask.ndim < arraySlice.ndim:
        mask = np.broadcast_to(~mask[..., np.newaxis], arraySlice.shape)
    maskedArray = np.ma.masked_array(arraySlice, mask=mask)
    # np.newaxis is to explicitly give the mask the same number of dimensions as arraySlice. For some reason need to do that.
    # maskedArray = np.where(mask[..., np.newaxis], arraySlice, np.nan)

    if returnTransform:
        return maskedArray, transform

    return maskedArray


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
        varda.log.error(f"Error evaluating formula '{formula}': {e}")
        return None
