"""
plot.py
Represents a saved plot in Varda.
"""

# standard library
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from .roi import ROI


@dataclass
class Plot:
    """
    Attributes:
        plot_type (str): The type of plot (e.g., "ROI", "Histogram").
        timestamp (str): The time when the plot was saved.
        data (Any): Data needed to reconstruct the plot.
    """

    plot_type: str
    timestamp: str
    data: Any

    @staticmethod
    def create(roi: ROI):
        """Factory method to create a new plot with a timestamp."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return Plot("ROI", timestamp, roi.meanSpectrum)
