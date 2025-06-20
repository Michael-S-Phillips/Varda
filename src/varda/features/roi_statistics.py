"""
Enhanced ROI statistics calculator for Varda.

This module provides functions to calculate detailed statistics
for regions of interest (ROIs) in hyperspectral imagery.
"""

import numpy as np
from scipy import stats
from typing import Dict, List, Tuple, Any, Optional
import logging

logger = logging.getLogger(__name__)


class ROIStatistics:
    """Class to calculate and store statistics for an ROI."""

    def __init__(self, roi_data: np.ndarray):
        """
        Initialize with the data array from within an ROI.

        Args:
            roi_data: Numpy array containing the spectral data within the ROI.
                      Shape should be (n_pixels, n_bands) or (n_pixels, y, x, n_bands)
        """
        # Ensure data is in the right shape
        if roi_data.ndim > 2:
            # Flatten spatial dimensions
            self.data = roi_data.reshape(-1, roi_data.shape[-1])
        else:
            self.data = roi_data

        self.n_pixels = self.data.shape[0]
        self.n_bands = self.data.shape[1]

        # Calculate basic statistics
        self._calculate_basic_stats()

    def _calculate_basic_stats(self):
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
        self._calculate_advanced_stats()

    def _calculate_advanced_stats(self):
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
            self._calculate_spectral_indices()

    def _calculate_spectral_indices(self):
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

    def get_summary(self) -> Dict[str, Any]:
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

    def get_band_stats(self, band_idx: int) -> Dict[str, Any]:
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

    def compare_bands(self, band1_idx: int, band2_idx: int) -> Dict[str, Any]:
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


def calculate_roi_stats(roi, image_data, wavelengths=None):
    """
    Calculate statistics for an ROI from image data.

    Args:
        roi: The ROI object (containing points or mask)
        image_data: The full image data array
        wavelengths: Optional wavelength values for each band

    Returns:
        ROIStatistics object
    """
    # Extract data for the ROI
    if hasattr(roi, "arraySlice") and roi.arraySlice is not None:
        # Use pre-calculated array slice if available
        roi_data = roi.arraySlice
    elif hasattr(roi, "points") and roi.points is not None:
        # Create mask from points and extract data
        mask = create_mask_from_points(roi.points, image_data.shape[:2])
        roi_data = image_data[mask]
    else:
        logger.error("ROI does not have valid points or array slice")
        return None

    # Create statistics object
    stats = ROIStatistics(roi_data)

    # Add wavelength information if available
    if wavelengths is not None:
        stats.wavelengths = wavelengths

    return stats


def create_mask_from_points(points, shape):
    """
    Create a binary mask from ROI points.

    Args:
        points: List of points defining the ROI
        shape: Shape of the image (height, width)

    Returns:
        Binary mask array
    """
    from skimage.draw import polygon

    # Convert points to the format needed by skimage.draw.polygon
    # Assuming points is a tuple/list of (x, y) coordinates
    if isinstance(points, tuple) and len(points) == 2:
        # Format is ([x1, x2, ...], [y1, y2, ...])
        x_coords, y_coords = points
    else:
        # Format is [(x1, y1), (x2, y2), ...]
        x_coords = [p[0] for p in points]
        y_coords = [p[1] for p in points]

    # Create mask
    mask = np.zeros(shape, dtype=bool)
    rr, cc = polygon(y_coords, x_coords, shape)
    mask[rr, cc] = True

    return mask


def compare_rois(roi_stats1, roi_stats2):
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
