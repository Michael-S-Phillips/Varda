# src/core/stretch/stretch_algorithms.py

import numpy as np
from skimage import exposure
from typing import Tuple, List, Optional, Dict, Any, Union
import logging

logger = logging.getLogger(__name__)


class StretchAlgorithm:
    """Base class for implementing different stretch algorithms.

    A stretch algorithm takes an image (or histogram data) and computes
    suitable min/max values for each channel (R,G,B) to enhance visualization.
    """

    @staticmethod
    def name() -> str:
        """Return the name of the stretch algorithm"""
        return "Base Stretch"

    @staticmethod
    def description() -> str:
        """Return a description of the stretch algorithm"""
        return "Base stretch algorithm"

    @staticmethod
    def parameters() -> Dict[str, Dict[str, Any]]:
        """Return parameters that can be adjusted for this algorithm"""
        return {}

    @staticmethod
    def compute_stretch(
        image_data: np.ndarray, **kwargs
    ) -> Tuple[float, float, float, float, float, float]:
        """Compute min/max values for R, G, B channels.

        Args:
            image_data: The image data array with shape (h, w, 3) for RGB
            **kwargs: Additional parameters specific to the algorithm

        Returns:
            Tuple of (minR, maxR, minG, maxG, minB, maxB)
        """
        raise NotImplementedError("Subclasses must implement this method")


class MinMaxStretch(StretchAlgorithm):
    """Simple min-max stretch that uses the full range of values in the image."""

    @staticmethod
    def name() -> str:
        return "Min-Max (Full Range)"

    @staticmethod
    def description() -> str:
        return "Stretches each channel to use the full range of values in the image"

    @staticmethod
    def parameters() -> Dict[str, Dict[str, Any]]:
        return {}

    @staticmethod
    def compute_stretch(
        image_data: np.ndarray, **kwargs
    ) -> Tuple[float, float, float, float, float, float]:
        """Compute min/max values for the full range of data."""
        if image_data.ndim != 3 or image_data.shape[2] < 3:
            # Handle grayscale or invalid data
            min_val = np.min(image_data)
            max_val = np.max(image_data)
            return min_val, max_val, min_val, max_val, min_val, max_val

        # Compute min/max for each channel
        minR = np.min(image_data[:, :, 0])
        maxR = np.max(image_data[:, :, 0])
        minG = np.min(image_data[:, :, 1])
        maxG = np.max(image_data[:, :, 1])
        minB = np.min(image_data[:, :, 2])
        maxB = np.max(image_data[:, :, 2])

        return minR, maxR, minG, maxG, minB, maxB


class PercentileStretch(StretchAlgorithm):
    """Percentile-based linear stretch."""

    @staticmethod
    def name() -> str:
        return "Percentile Stretch"

    @staticmethod
    def description() -> str:
        return "Stretches to exclude outliers based on percentiles"

    @staticmethod
    def parameters() -> Dict[str, Dict[str, Any]]:
        return {
            "low_percentile": {
                "type": float,
                "default": 2.0,
                "min": 0.0,
                "max": 49.0,
                "description": "Lower percentile to exclude",
            },
            "high_percentile": {
                "type": float,
                "default": 98.0,
                "min": 51.0,
                "max": 100.0,
                "description": "Upper percentile to exclude",
            },
        }

    @staticmethod
    def compute_stretch(
        image_data: np.ndarray, **kwargs
    ) -> Tuple[float, float, float, float, float, float]:
        """Compute min/max values based on percentiles."""
        low_percentile = kwargs.get("low_percentile", 2.0)
        high_percentile = kwargs.get("high_percentile", 98.0)

        if image_data.ndim != 3 or image_data.shape[2] < 3:
            # Handle grayscale or invalid data
            p_low = np.percentile(image_data, low_percentile)
            p_high = np.percentile(image_data, high_percentile)
            return p_low, p_high, p_low, p_high, p_low, p_high

        # Compute percentiles for each channel
        minR = np.percentile(image_data[:, :, 0], low_percentile)
        maxR = np.percentile(image_data[:, :, 0], high_percentile)
        minG = np.percentile(image_data[:, :, 1], low_percentile)
        maxG = np.percentile(image_data[:, :, 1], high_percentile)
        minB = np.percentile(image_data[:, :, 2], low_percentile)
        maxB = np.percentile(image_data[:, :, 2], high_percentile)

        return minR, maxR, minG, maxG, minB, maxB


class GaussianStretch(StretchAlgorithm):
    """Gaussian stretch based on mean and standard deviation."""

    @staticmethod
    def name() -> str:
        return "Gaussian Stretch"

    @staticmethod
    def description() -> str:
        return "Stretches using mean and standard deviation"

    @staticmethod
    def parameters() -> Dict[str, Dict[str, Any]]:
        return {
            "sigma_factor": {
                "type": float,
                "default": 2.0,
                "min": 0.5,
                "max": 5.0,
                "description": "Number of standard deviations from mean",
            }
        }

    @staticmethod
    def compute_stretch(
        image_data: np.ndarray, **kwargs
    ) -> Tuple[float, float, float, float, float, float]:
        """Compute min/max values based on mean and std deviation."""
        sigma_factor = kwargs.get("sigma_factor", 2.0)

        if image_data.ndim != 3 or image_data.shape[2] < 3:
            # Handle grayscale or invalid data
            mean = np.mean(image_data)
            std = np.std(image_data)
            min_val = max(np.min(image_data), mean - sigma_factor * std)
            max_val = min(np.max(image_data), mean + sigma_factor * std)
            return min_val, max_val, min_val, max_val, min_val, max_val

        # Compute mean and std for each channel
        meanR = np.mean(image_data[:, :, 0])
        stdR = np.std(image_data[:, :, 0])
        meanG = np.mean(image_data[:, :, 1])
        stdG = np.std(image_data[:, :, 1])
        meanB = np.mean(image_data[:, :, 2])
        stdB = np.std(image_data[:, :, 2])

        # Calculate min/max values based on mean and std
        minR = max(np.min(image_data[:, :, 0]), meanR - sigma_factor * stdR)
        maxR = min(np.max(image_data[:, :, 0]), meanR + sigma_factor * stdR)
        minG = max(np.min(image_data[:, :, 1]), meanG - sigma_factor * stdG)
        maxG = min(np.max(image_data[:, :, 1]), meanG + sigma_factor * stdG)
        minB = max(np.min(image_data[:, :, 2]), meanB - sigma_factor * stdB)
        maxB = min(np.max(image_data[:, :, 2]), meanB + sigma_factor * stdB)

        return minR, maxR, minG, maxG, minB, maxB


class SquareRootStretch(StretchAlgorithm):
    """Square root stretch that enhances lower values."""

    @staticmethod
    def name() -> str:
        return "Square Root Stretch"

    @staticmethod
    def description() -> str:
        return "Enhances lower values using square root transformation"

    @staticmethod
    def parameters() -> Dict[str, Dict[str, Any]]:
        return {}

    @staticmethod
    def compute_stretch(
        image_data: np.ndarray, **kwargs
    ) -> Tuple[float, float, float, float, float, float]:
        """Compute min/max values for square root transform."""
        # We need to shift the data to be non-negative for square root
        if image_data.ndim != 3 or image_data.shape[2] < 3:
            # Handle grayscale or invalid data
            min_val = np.min(image_data)
            max_val = np.max(image_data)

            # Apply square root transform to the max to simulate stretching effect
            transformed_max = np.sqrt(max_val - min_val)
            return (
                min_val,
                min_val + transformed_max**2,
                min_val,
                min_val + transformed_max**2,
                min_val,
                min_val + transformed_max**2,
            )

        # Compute min/max for each channel
        minR = np.min(image_data[:, :, 0])
        maxR = np.max(image_data[:, :, 0])
        minG = np.min(image_data[:, :, 1])
        maxG = np.max(image_data[:, :, 1])
        minB = np.min(image_data[:, :, 2])
        maxB = np.max(image_data[:, :, 2])

        # Apply square root transform to the max to simulate stretching effect
        transformed_maxR = np.sqrt(maxR - minR)
        transformed_maxG = np.sqrt(maxG - minG)
        transformed_maxB = np.sqrt(maxB - minB)

        return (
            minR,
            minR + transformed_maxR**2,
            minG,
            minG + transformed_maxG**2,
            minB,
            minB + transformed_maxB**2,
        )


class LogarithmicStretch(StretchAlgorithm):
    """Logarithmic stretch that enhances detail in dark areas."""

    @staticmethod
    def name() -> str:
        return "Logarithmic Stretch"

    @staticmethod
    def description() -> str:
        return "Enhances detail in dark areas using logarithmic transformation"

    @staticmethod
    def parameters() -> Dict[str, Dict[str, Any]]:
        return {
            "gain": {
                "type": float,
                "default": 1.0,
                "min": 0.1,
                "max": 10.0,
                "description": "Gain factor for log transform",
            }
        }

    @staticmethod
    def compute_stretch(
        image_data: np.ndarray, **kwargs
    ) -> Tuple[float, float, float, float, float, float]:
        """Compute min/max values for logarithmic transform."""
        gain = kwargs.get("gain", 1.0)

        # Compute min-max first
        if image_data.ndim != 3 or image_data.shape[2] < 3:
            # Handle grayscale or invalid data
            min_val = np.min(image_data)
            max_val = np.max(image_data)

            # Apply log transform to the max to simulate stretching effect
            log_max = np.log1p((max_val - min_val) * gain)
            return (
                min_val,
                min_val + np.exp(log_max) - 1,
                min_val,
                min_val + np.exp(log_max) - 1,
                min_val,
                min_val + np.exp(log_max) - 1,
            )

        # Compute min/max for each channel
        minR = np.min(image_data[:, :, 0])
        maxR = np.max(image_data[:, :, 0])
        minG = np.min(image_data[:, :, 1])
        maxG = np.max(image_data[:, :, 1])
        minB = np.min(image_data[:, :, 2])
        maxB = np.max(image_data[:, :, 2])

        # Apply log transform to the max to simulate stretching effect
        log_maxR = np.log1p((maxR - minR) * gain)
        log_maxG = np.log1p((maxG - minG) * gain)
        log_maxB = np.log1p((maxB - minB) * gain)

        return (
            minR,
            minR + np.exp(log_maxR) - 1,
            minG,
            minG + np.exp(log_maxG) - 1,
            minB,
            minB + np.exp(log_maxB) - 1,
        )


class DecorrelationStretch(StretchAlgorithm):
    """Decorrelation stretch that enhances color differences by decorrelating the RGB channels."""

    @staticmethod
    def name() -> str:
        return "Decorrelation Stretch"

    @staticmethod
    def description() -> str:
        return "Enhances color differences by decorrelating RGB channels"

    @staticmethod
    def parameters() -> Dict[str, Dict[str, Any]]:
        return {
            "scaling_factor": {
                "type": float,
                "default": 2.5,
                "min": 1.0,
                "max": 5.0,
                "description": "Scaling factor for eigenvalues",
            }
        }

    @staticmethod
    def compute_stretch(
        image_data: np.ndarray, **kwargs
    ) -> Tuple[float, float, float, float, float, float]:
        """Compute decorrelation stretch values for RGB channels.

        This method applies a principal component analysis (PCA) to the RGB channels
        to decorrelate them, enhancing the color differences.

        Args:
            image_data: The image data with shape (height, width, bands)
            **kwargs: Additional parameters:
                - scaling_factor: Scaling factor for eigenvalues (default: 2.5)

        Returns:
            Tuple of (minR, maxR, minG, maxG, minB, maxB)
        """
        if image_data.ndim != 3 or image_data.shape[2] < 3:
            logger.warning(
                "Cannot do decorrelation on non-RGB data, falling back to min-max"
            )
            return MinMaxStretch.compute_stretch(image_data)

        try:
            # Get the scaling factor
            scaling_factor = kwargs.get("scaling_factor", 2.5)

            # Use only the first 3 bands (RGB) for decorrelation
            rgb_data = image_data[:, :, :3]

            # Reshape to 2D for PCA: (pixels, channels)
            h, w, c = rgb_data.shape
            pixels = h * w
            reshaped_data = rgb_data.reshape(pixels, c)

            # Remove NaN values if any
            valid_pixels = ~np.isnan(reshaped_data).any(axis=1)
            if not np.all(valid_pixels):
                logger.warning(
                    f"Found {pixels - np.sum(valid_pixels)} NaN pixels in data"
                )
                reshaped_data = reshaped_data[valid_pixels]

            # Compute mean and covariance
            mean_vec = np.mean(reshaped_data, axis=0)
            cov_mat = np.cov(reshaped_data, rowvar=False)

            # Compute eigenvalues and eigenvectors
            eigenvals, eigenvecs = np.linalg.eigh(cov_mat)

            # Sort eigenvalues and eigenvectors in descending order
            idx = eigenvals.argsort()[::-1]
            eigenvals = eigenvals[idx]
            eigenvecs = eigenvecs[:, idx]

            # Store data for the transform function
            kwargs["decorr_mean"] = mean_vec
            kwargs["decorr_eigenvecs"] = eigenvecs
            kwargs["decorr_eigenvals"] = eigenvals
            kwargs["decorr_scaling"] = scaling_factor

            # Apply the decorrelation transform
            transformed_data = DecorrelationStretch._apply_decorrelation(
                rgb_data, mean_vec, eigenvecs, eigenvals, scaling_factor
            )

            # Compute the min/max values from the transformed data
            minR = np.nanmin(transformed_data[:, :, 0])
            maxR = np.nanmax(transformed_data[:, :, 0])
            minG = np.nanmin(transformed_data[:, :, 1])
            maxG = np.nanmax(transformed_data[:, :, 1])
            minB = np.nanmin(transformed_data[:, :, 2])
            maxB = np.nanmax(transformed_data[:, :, 2])

            # Ensure we have reasonable values
            if not (
                np.isfinite(minR)
                and np.isfinite(maxR)
                and np.isfinite(minG)
                and np.isfinite(maxG)
                and np.isfinite(minB)
                and np.isfinite(maxB)
            ):
                logger.error(
                    "Non-finite values in decorrelation result, falling back to min-max"
                )
                return MinMaxStretch.compute_stretch(image_data)

            return minR, maxR, minG, maxG, minB, maxB

        except Exception as e:
            logger.error(f"Error computing decorrelation stretch: {e}")
            # Fall back to min-max on error
            return MinMaxStretch.compute_stretch(image_data)

    @staticmethod
    def _apply_decorrelation(
        image_data: np.ndarray,
        mean_vec: np.ndarray,
        eigenvecs: np.ndarray,
        eigenvals: np.ndarray,
        scaling_factor: float,
    ) -> np.ndarray:
        """Apply the decorrelation transformation to the image data.

        Args:
            image_data: RGB image data with shape (height, width, 3)
            mean_vec: Mean vector from PCA
            eigenvecs: Eigenvectors from PCA
            eigenvals: Eigenvalues from PCA
            scaling_factor: Scaling factor for eigenvalues

        Returns:
            Transformed image data with the same shape as input
        """
        h, w, c = image_data.shape

        # Reshape to 2D: (pixels, channels)
        reshaped_data = image_data.reshape(h * w, c)

        # Center the data
        centered_data = reshaped_data - mean_vec

        # Transform to eigenspace
        pca_data = np.dot(centered_data, eigenvecs)

        # Scale the data
        scaled_eigenvals = eigenvals * scaling_factor
        scale_factors = np.sqrt(scaled_eigenvals / np.maximum(eigenvals, 1e-10))
        scaled_pca_data = pca_data * scale_factors

        # Transform back to image space
        transformed_data = np.dot(scaled_pca_data, eigenvecs.T) + mean_vec

        # Reshape back to image shape
        transformed_data = transformed_data.reshape(h, w, c)

        # Clip to valid range
        transformed_data = np.clip(transformed_data, 0, 1)

        return transformed_data


class HistogramEqualization(StretchAlgorithm):
    """Stretch based on histogram equalization for contrast enhancement."""

    @staticmethod
    def name() -> str:
        return "Histogram Equalization"

    @staticmethod
    def description() -> str:
        return "Enhances contrast by equalizing the image histogram"

    @staticmethod
    def parameters() -> Dict[str, Dict[str, Any]]:
        return {}

    @staticmethod
    def compute_stretch(
        image_data: np.ndarray, **kwargs
    ) -> Tuple[float, float, float, float, float, float]:
        """Compute min/max values based on histogram equalization."""
        try:
            if image_data.ndim != 3 or image_data.shape[2] < 3:
                # Handle grayscale
                # Apply histogram equalization and get min/max
                equalized = exposure.equalize_hist(image_data)
                min_val = np.nanmin(equalized)
                max_val = np.nanmax(equalized)
                return min_val, max_val, min_val, max_val, min_val, max_val

            # For RGB, apply histogram equalization to each channel
            equalized = np.zeros_like(image_data[:, :, :3])

            for i in range(3):  # Equalize R, G, B channels
                equalized[:, :, i] = exposure.equalize_hist(image_data[:, :, i])

            # Get min/max values from equalized image
            minR = np.nanmin(equalized[:, :, 0])
            maxR = np.nanmax(equalized[:, :, 0])
            minG = np.nanmin(equalized[:, :, 1])
            maxG = np.nanmax(equalized[:, :, 1])
            minB = np.nanmin(equalized[:, :, 2])
            maxB = np.nanmax(equalized[:, :, 2])

            # Store flag for histogram equalization in kwargs
            kwargs["use_histeq"] = True

            return minR, maxR, minG, maxG, minB, maxB

        except Exception as e:
            logger.error(f"Error computing histogram equalization: {e}")
            # Fall back to min-max on error
            return MinMaxStretch.compute_stretch(image_data)


class AdaptiveEqualization(StretchAlgorithm):
    """Adaptive contrast enhancement using CLAHE."""

    @staticmethod
    def name() -> str:
        return "Adaptive Equalization (CLAHE)"

    @staticmethod
    def description() -> str:
        return "Enhances local contrast using Contrast Limited Adaptive Histogram Equalization"

    @staticmethod
    def parameters() -> Dict[str, Dict[str, Any]]:
        return {
            "clip_limit": {
                "type": float,
                "default": 0.01,
                "min": 0.001,
                "max": 0.05,
                "description": "Clipping limit for contrast enhancement",
            },
            "tile_size": {
                "type": int,
                "default": 8,
                "min": 4,
                "max": 16,
                "description": "Size of grid tiles (as a fraction of image size)",
            },
        }

    @staticmethod
    def compute_stretch(
        image_data: np.ndarray, **kwargs
    ) -> Tuple[float, float, float, float, float, float]:
        """Compute min/max values based on adaptive equalization."""
        try:
            # Get parameters
            clip_limit = kwargs.get("clip_limit", 0.01)
            tile_size = kwargs.get("tile_size", 8)

            # Calculate grid size based on tile_size parameter
            h, w = image_data.shape[:2]
            grid_size = max(2, min(16, int(min(h, w) / (2**tile_size))))

            if image_data.ndim != 3 or image_data.shape[2] < 3:
                # Handle grayscale
                # Apply CLAHE and get min/max
                equalized = exposure.equalize_adapthist(
                    image_data, clip_limit=clip_limit, kernel_size=grid_size
                )
                min_val = np.nanmin(equalized)
                max_val = np.nanmax(equalized)
                return min_val, max_val, min_val, max_val, min_val, max_val

            # For RGB, apply CLAHE to each channel
            equalized = np.zeros_like(image_data[:, :, :3])

            for i in range(3):  # Apply to R, G, B channels
                equalized[:, :, i] = exposure.equalize_adapthist(
                    image_data[:, :, i], clip_limit=clip_limit, kernel_size=grid_size
                )

            # Get min/max values from equalized image
            minR = np.nanmin(equalized[:, :, 0])
            maxR = np.nanmax(equalized[:, :, 0])
            minG = np.nanmin(equalized[:, :, 1])
            maxG = np.nanmax(equalized[:, :, 1])
            minB = np.nanmin(equalized[:, :, 2])
            maxB = np.nanmax(equalized[:, :, 2])

            # Store CLAHE parameters for applying the transform
            kwargs["use_clahe"] = True
            kwargs["clahe_clip_limit"] = clip_limit
            kwargs["clahe_grid_size"] = grid_size

            return minR, maxR, minG, maxG, minB, maxB

        except Exception as e:
            logger.error(f"Error computing adaptive equalization: {e}")
            # Fall back to min-max on error
            return MinMaxStretch.compute_stretch(image_data)


# Registry of available algorithms
STRETCH_ALGORITHMS = {
    "min_max": MinMaxStretch.compute_stretch,  # Use the static method directly
    "percentile_1": lambda img, **kw: PercentileStretch.compute_stretch(
        img, low_percentile=1.0, high_percentile=99.0, **kw
    ),
    "percentile_2": lambda img, **kw: PercentileStretch.compute_stretch(
        img, low_percentile=2.0, high_percentile=98.0, **kw
    ),
    "percentile_5": lambda img, **kw: PercentileStretch.compute_stretch(
        img, low_percentile=5.0, high_percentile=95.0, **kw
    ),
    "gaussian_2sigma": lambda img, **kw: GaussianStretch.compute_stretch(
        img, sigma_factor=2.0, **kw
    ),
    "gaussian_3sigma": lambda img, **kw: GaussianStretch.compute_stretch(
        img, sigma_factor=3.0, **kw
    ),
    "square_root": SquareRootStretch.compute_stretch,  # Use the static method directly
    "logarithmic": LogarithmicStretch.compute_stretch,  # Use the static method directly
    "decorrelation": DecorrelationStretch.compute_stretch,  # Use the static method directly
    "histogram_eq": HistogramEqualization.compute_stretch,  # Use the static method directly
    "adaptive_eq": AdaptiveEqualization.compute_stretch,  # Use the static method directly
}

# Dictionary of user-friendly names
STRETCH_NAMES = {
    "min_max": "Min-Max (Full Range)",
    "percentile_1": "Linear 1%",
    "percentile_2": "Linear 2%",
    "percentile_5": "Linear 5%",
    "gaussian_2sigma": "Gaussian (±2σ)",
    "gaussian_3sigma": "Gaussian (±3σ)",
    "square_root": "Square Root",
    "logarithmic": "Logarithmic",
    "decorrelation": "Decorrelation Stretch",
    "histogram_eq": "Histogram Equalization",
    "adaptive_eq": "Adaptive Equalization (CLAHE)",
}


def get_available_stretches():
    """Get a list of available stretch algorithms."""
    return [(key, STRETCH_NAMES[key]) for key in STRETCH_ALGORITHMS.keys()]


def compute_stretch(
    algorithm_id: str, image_data: np.ndarray, **kwargs
) -> Tuple[float, float, float, float, float, float]:
    """Compute a stretch using the specified algorithm.

    Args:
        algorithm_id: The ID of the algorithm to use
        image_data: The image data to compute the stretch for
        **kwargs: Additional parameters for the algorithm

    Returns:
        Tuple of (minR, maxR, minG, maxG, minB, maxB)
    """
    if algorithm_id not in STRETCH_ALGORITHMS:
        logger.warning(f"Unknown stretch algorithm: {algorithm_id}, using min-max")
        algorithm_id = "min_max"

    return STRETCH_ALGORITHMS[algorithm_id](image_data, **kwargs)


def apply_stretch_transform(
    image_data: np.ndarray,
    algorithm_id: str,
    stretch_values: Tuple[float, float, float, float, float, float],
    **kwargs,
) -> np.ndarray:
    """Apply a transform to the image data based on the algorithm and stretch values.

    This is used for algorithms like decorrelation stretch that need to transform the image
    data differently than just applying min/max values.

    Args:
        image_data: The image data to transform
        algorithm_id: The ID of the algorithm to use
        stretch_values: The stretch values computed by compute_stretch
        **kwargs: Additional parameters containing transform data

    Returns:
        The transformed image data
    """
    # For most algorithms, we don't need to transform the data
    # Just return the original
    if algorithm_id not in ["decorrelation", "histogram_eq", "adaptive_eq"]:
        return image_data

    # Get the relevant part of the image data (first 3 bands for RGB)
    if image_data.ndim == 3 and image_data.shape[2] >= 3:
        rgb_data = image_data[:, :, :3]
    else:
        rgb_data = image_data

    # For decorrelation stretch
    if algorithm_id == "decorrelation" and "decorr_eigenvecs" in kwargs:
        try:
            # Use the helper method to apply the transformation
            return DecorrelationStretch._apply_decorrelation(
                rgb_data,
                kwargs["decorr_mean"],
                kwargs["decorr_eigenvecs"],
                kwargs["decorr_eigenvals"],
                kwargs["decorr_scaling"],
            )
        except Exception as e:
            logger.error(f"Error applying decorrelation transform: {e}")
            return image_data

    # For histogram equalization
    elif algorithm_id == "histogram_eq" and kwargs.get("use_histeq", False):
        try:
            # Apply histogram equalization to each channel
            h, w = rgb_data.shape[:2]
            result = np.zeros_like(rgb_data)

            if rgb_data.ndim == 3:
                for i in range(rgb_data.shape[2]):
                    result[:, :, i] = exposure.equalize_hist(rgb_data[:, :, i])
            else:
                result = exposure.equalize_hist(rgb_data)

            return result

        except Exception as e:
            logger.error(f"Error applying histogram equalization: {e}")
            return image_data

    # For adaptive equalization (CLAHE)
    elif algorithm_id == "adaptive_eq" and kwargs.get("use_clahe", False):
        try:
            # Get CLAHE parameters
            clip_limit = kwargs.get("clahe_clip_limit", 0.01)
            grid_size = kwargs.get("clahe_grid_size", 8)

            # Apply CLAHE to each channel
            h, w = rgb_data.shape[:2]
            result = np.zeros_like(rgb_data)

            if rgb_data.ndim == 3:
                for i in range(rgb_data.shape[2]):
                    result[:, :, i] = exposure.equalize_adapthist(
                        rgb_data[:, :, i], clip_limit=clip_limit, kernel_size=grid_size
                    )
            else:
                result = exposure.equalize_adapthist(
                    rgb_data, clip_limit=clip_limit, kernel_size=grid_size
                )

            return result

        except Exception as e:
            logger.error(f"Error applying adaptive equalization: {e}")
            return image_data

    # Default: return original data
    return image_data
