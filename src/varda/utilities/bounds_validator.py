"""
Bounds validation utilities for safe array operations.
Provides consistent bounds checking across all image access operations.
"""

import numpy as np
import logging
from typing import Tuple, Optional, Union

logger = logging.getLogger(__name__)


class BoundsValidator:
    """Utility class for validating and constraining array access operations."""

    @staticmethod
    def validate_pixel_coordinates(
        x: int, y: int, image_shape: Tuple[int, ...], allow_clipping: bool = False
    ) -> Tuple[bool, Tuple[int, int]]:
        """
        Validate pixel coordinates against image bounds.

        Args:
            x: X coordinate (column)
            y: Y coordinate (row)
            image_shape: Shape of the image array (height, width, bands)
            allow_clipping: If True, clip coordinates to valid range

        Returns:
            Tuple of (is_valid, (clipped_x, clipped_y))
        """
        if len(image_shape) < 2:
            logger.error(f"Invalid image shape: {image_shape}")
            return False, (x, y)

        height, width = image_shape[0], image_shape[1]

        # Check if coordinates are within bounds
        x_valid = 0 <= x < width
        y_valid = 0 <= y < height

        if x_valid and y_valid:
            return True, (x, y)

        if not allow_clipping:
            logger.warning(
                f"Coordinates ({x}, {y}) are outside image bounds "
                f"(width: {width}, height: {height})"
            )
            return False, (x, y)

        # Clip coordinates to valid range
        clipped_x = max(0, min(x, width - 1))
        clipped_y = max(0, min(y, height - 1))

        if clipped_x != x or clipped_y != y:
            logger.info(
                f"Clipped coordinates from ({x}, {y}) to ({clipped_x}, {clipped_y}) "
                f"for image bounds (width: {width}, height: {height})"
            )

        return True, (clipped_x, clipped_y)

    @staticmethod
    def safe_pixel_access(
        raster: np.ndarray,
        x: int,
        y: int,
        default_value: Optional[Union[float, np.ndarray]] = None,
    ) -> np.ndarray:
        """
        Safely access pixel data with bounds checking.

        Args:
            raster: Image array with shape (height, width, bands)
            x: X coordinate (column)
            y: Y coordinate (row)
            default_value: Value to return if coordinates are invalid

        Returns:
            Spectral data array for the pixel, or default_value if invalid
        """
        try:
            is_valid, (safe_x, safe_y) = BoundsValidator.validate_pixel_coordinates(
                x, y, raster.shape, allow_clipping=True
            )

            if not is_valid:
                if default_value is not None:
                    if isinstance(default_value, np.ndarray):
                        return default_value
                    else:
                        return np.full(
                            raster.shape[2], default_value, dtype=raster.dtype
                        )
                else:
                    # Return zeros array matching the spectral dimension
                    return np.zeros(raster.shape[2], dtype=raster.dtype)

            # Safe access with validated coordinates
            pixel_data = raster[safe_y, safe_x, :]

            # Validate the returned data
            if np.any(np.isnan(pixel_data)) or np.any(np.isinf(pixel_data)):
                logger.warning(f"Invalid data detected at pixel ({safe_x}, {safe_y})")
                # Replace invalid values with zeros
                pixel_data = np.nan_to_num(pixel_data, nan=0.0, posinf=0.0, neginf=0.0)

            return pixel_data

        except Exception as e:
            logger.error(f"Error accessing pixel data at ({x}, {y}): {e}")
            if default_value is not None:
                if isinstance(default_value, np.ndarray):
                    return default_value
                else:
                    return np.full(raster.shape[2], default_value, dtype=raster.dtype)
            else:
                return np.zeros(raster.shape[2], dtype=raster.dtype)

    @staticmethod
    def validate_roi_bounds(
        x: int,
        y: int,
        width: int,
        height: int,
        image_shape: Tuple[int, ...],
        allow_clipping: bool = True,
    ) -> Tuple[bool, Tuple[int, int, int, int]]:
        """
        Validate and optionally clip ROI bounds to image dimensions.

        Args:
            x: ROI top-left X coordinate
            y: ROI top-left Y coordinate
            width: ROI width
            height: ROI height
            image_shape: Shape of the image array
            allow_clipping: If True, clip ROI to fit within image

        Returns:
            Tuple of (is_valid, (clipped_x, clipped_y, clipped_width, clipped_height))
        """
        if len(image_shape) < 2:
            logger.error(f"Invalid image shape: {image_shape}")
            return False, (x, y, width, height)

        img_height, img_width = image_shape[0], image_shape[1]

        # Check if ROI is completely within bounds
        if (
            x >= 0
            and y >= 0
            and x + width <= img_width
            and y + height <= img_height
            and width > 0
            and height > 0
        ):
            return True, (x, y, width, height)

        if not allow_clipping:
            logger.warning(
                f"ROI ({x}, {y}, {width}, {height}) exceeds image bounds "
                f"(width: {img_width}, height: {img_height})"
            )
            return False, (x, y, width, height)

        # Clip ROI to image bounds
        clipped_x = max(0, x)
        clipped_y = max(0, y)
        clipped_width = min(width, img_width - clipped_x)
        clipped_height = min(height, img_height - clipped_y)

        # Ensure minimum size
        clipped_width = max(1, clipped_width)
        clipped_height = max(1, clipped_height)

        if (
            clipped_x != x
            or clipped_y != y
            or clipped_width != width
            or clipped_height != height
        ):
            logger.info(
                f"Clipped ROI from ({x}, {y}, {width}, {height}) to "
                f"({clipped_x}, {clipped_y}, {clipped_width}, {clipped_height})"
            )

        return True, (clipped_x, clipped_y, clipped_width, clipped_height)

    @staticmethod
    def safe_roi_access(
        raster: np.ndarray, x: int, y: int, width: int, height: int
    ) -> np.ndarray:
        """
        Safely access ROI data with bounds checking.

        Args:
            raster: Image array with shape (height, width, bands)
            x: ROI top-left X coordinate
            y: ROI top-left Y coordinate
            width: ROI width
            height: ROI height

        Returns:
            ROI data array with shape (clipped_height, clipped_width, bands)
        """
        try:
            is_valid, (safe_x, safe_y, safe_width, safe_height) = (
                BoundsValidator.validate_roi_bounds(
                    x, y, width, height, raster.shape, allow_clipping=True
                )
            )

            if not is_valid or safe_width <= 0 or safe_height <= 0:
                # Return minimal ROI if validation fails
                return np.zeros((1, 1, raster.shape[2]), dtype=raster.dtype)

            # Safe ROI access with validated bounds
            roi_data = raster[
                safe_y : safe_y + safe_height, safe_x : safe_x + safe_width, :
            ]

            # Validate the returned data
            if np.any(np.isnan(roi_data)) or np.any(np.isinf(roi_data)):
                logger.warning(
                    f"Invalid data detected in ROI ({safe_x}, {safe_y}, {safe_width}, {safe_height})"
                )
                roi_data = np.nan_to_num(roi_data, nan=0.0, posinf=0.0, neginf=0.0)

            return roi_data

        except Exception as e:
            logger.error(
                f"Error accessing ROI data at ({x}, {y}, {width}, {height}): {e}"
            )
            return np.zeros((1, 1, raster.shape[2]), dtype=raster.dtype)
