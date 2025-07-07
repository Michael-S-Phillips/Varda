import logging
from typing import Dict, Any, Tuple

import numpy as np
from scipy import stats

from varda.app.services import roi_utils
from varda.core.entities import ROI, Image

logger = logging.getLogger(__name__)


# TODO: THis seems to be a bit broken maybe. Calculating statistics resulted in an error.
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
        mask = roi_utils.createROIMaskAlternative(roi.points, imageData.shape[:2])
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


def showStatisticsDialog(roi, stats):
    """Show a dialog with ROI statistics"""
    from PyQt6.QtWidgets import (
        QWidget,
        QDialog,
        QTabWidget,
        QVBoxLayout,
        QTableWidget,
        QTableWidgetItem,
    )

    dialog = QDialog()
    dialog.setWindowTitle(f"Statistics for ROI: {roi.name}")
    dialog.resize(800, 600)

    layout = QVBoxLayout(dialog)
    tab_widget = QTabWidget()

    # Summary tab
    summary_widget = QWidget()
    summary_layout = QVBoxLayout(summary_widget)
    summary_table = QTableWidget()
    summary_table.setColumnCount(2)
    summary_table.setHorizontalHeaderLabels(["Property", "Value"])

    # Add basic properties
    properties = [
        ("Number of pixels", stats.n_pixels),
        ("Number of bands", stats.n_bands),
        ("Area (pixels)", stats.n_pixels),
        ("Mean values", "See Band Statistics Tab"),
        (
            "Created",
            (
                roi.creation_time.strftime("%Y-%m-%d %H:%M:%S")
                if hasattr(roi, "creation_time")
                else "Unknown"
            ),
        ),
    ]

    summary_table.setRowCount(len(properties))
    for i, (prop, value) in enumerate(properties):
        summary_table.setItem(i, 0, QTableWidgetItem(prop))
        summary_table.setItem(i, 1, QTableWidgetItem(str(value)))

    summary_layout.addWidget(summary_table)
    tab_widget.addTab(summary_widget, "Summary")

    # Band statistics tab
    band_widget = QWidget()
    band_layout = QVBoxLayout(band_widget)
    band_table = QTableWidget()

    # Set up columns for band statistics
    stats_columns = [
        "Band",
        "Mean",
        "Median",
        "Std Dev",
        "Min",
        "Max",
        "25%",
        "75%",
    ]
    band_table.setColumnCount(len(stats_columns))
    band_table.setHorizontalHeaderLabels(stats_columns)

    # Add rows for each band
    band_table.setRowCount(stats.n_bands)
    for i in range(stats.n_bands):
        band_stats = stats.getBandStats(i)
        band_table.setItem(i, 0, QTableWidgetItem(str(i)))
        band_table.setItem(i, 1, QTableWidgetItem(f"{band_stats['mean']:.4f}"))
        band_table.setItem(i, 2, QTableWidgetItem(f"{band_stats['median']:.4f}"))
        band_table.setItem(i, 3, QTableWidgetItem(f"{band_stats['std_dev']:.4f}"))
        band_table.setItem(i, 4, QTableWidgetItem(f"{band_stats['min']:.4f}"))
        band_table.setItem(i, 5, QTableWidgetItem(f"{band_stats['max']:.4f}"))
        band_table.setItem(i, 6, QTableWidgetItem(f"{band_stats['percentile_25']:.4f}"))
        band_table.setItem(i, 7, QTableWidgetItem(f"{band_stats['percentile_75']:.4f}"))

    band_layout.addWidget(band_table)
    tab_widget.addTab(band_widget, "Band Statistics")

    # Add histogram tab if matplotlib is available
    try:
        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg

        hist_widget = QWidget()
        hist_layout = QVBoxLayout(hist_widget)

        # Create figure and canvas
        fig, ax = plt.subplots(figsize=(8, 6))
        canvas = FigureCanvasQTAgg(fig)

        # Plot histogram for the first band
        bin_centers, hist_values = stats.histogram(0)
        ax.bar(
            bin_centers,
            hist_values,
            width=((bin_centers[1] - bin_centers[0]) if len(bin_centers) > 1 else 0.1),
        )
        ax.set_title(f"Histogram for Band 0")
        ax.set_xlabel("Value")
        ax.set_ylabel("Frequency")

        hist_layout.addWidget(canvas)
        tab_widget.addTab(hist_widget, "Histogram")
    except ImportError:
        pass  # Skip histogram tab if matplotlib is not available

    layout.addWidget(tab_widget)
    dialog.setLayout(layout)
    dialog.exec()
