# src/varda/app/services/roi_service.py
import logging
import uuid
import numpy as np
from typing import List, Tuple, Dict, Optional, Any

from varda.app.models.roi import ROI
from varda.app.models.roi_models import ROIMode
from varda.app.services.geospatial_service import GeospatialService
from varda.core.data import ProjectContext

logger = logging.getLogger(__name__)


def create_roi(
    self,
    points: List[Tuple[float, float]],
    image_index: int,
    color: Tuple[int, int, int, int],
    mode: ROIMode,
) -> ROI:
    """Create a new ROI and save it to the project"""
    # Generate unique ID
    roi_id = f"roi_{uuid.uuid4().hex[:8]}"

    # Calculate geo coordinates if available
    geo_points = None
    try:
        image = self._get_image(image_index)
        if image and image.metadata.hasGeospatialData:
            px_list = [p[0] for p in points]
            py_list = [p[1] for p in points]
            lon_list, lat_list = self.geospatial_service.pixels_to_geo(
                image, px_list, py_list
            )
            geo_points = list(zip(lon_list, lat_list))
    except Exception as e:
        logger.warning(f"Failed to calculate geo coordinates: {e}")

    # Create ROI object
    roi = ROI(
        id=roi_id,
        points=points,
        image_index=image_index,
        color=color,
        geo_points=geo_points,
        mode=mode,
    )

    # Save to project
    self._save_roi(roi)

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
    for key, value in roi.custom_data.values.items():
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
