"""
Domain entity for plots in Varda.

This module defines the Plot class, which represents a plot of spectral data
extracted from a region of interest (ROI) in a hyperspectral image.
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

import numpy as np


@dataclass
class Plot:
    """
    Data representation of a spectral plot.
    
    A plot contains spectral data extracted from a region of interest (ROI)
    in a hyperspectral image, along with metadata about the plot.
    """

    name: str
    data: Optional[np.ndarray] = None
    wavelengths: Optional[np.ndarray] = None
    roi_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def serialize(self) -> Dict[str, Any]:
        """
        Serialize the plot into a JSON-compatible dictionary.

        Returns:
            Dict[str, Any]: The serialized plot.
        """
        # Convert numpy arrays to lists for serialization
        data = self.data.tolist() if self.data is not None else None
        wavelengths = self.wavelengths.tolist() if self.wavelengths is not None else None
        
        return {
            "name": self.name,
            "data": data,
            "wavelengths": wavelengths,
            "roi_id": self.roi_id,
            "metadata": self.metadata,
        }

    @classmethod
    def deserialize(cls, data: Dict[str, Any]) -> "Plot":
        """
        Create a Plot instance from serialized data.

        Args:
            data: The serialized plot.

        Returns:
            Plot: The deserialized Plot instance.
        """
        # Convert lists back to numpy arrays
        plot_data = np.array(data.get("data")) if data.get("data") is not None else None
        wavelengths = np.array(data.get("wavelengths")) if data.get("wavelengths") is not None else None
        
        return cls(
            name=data.get("name", ""),
            data=plot_data,
            wavelengths=wavelengths,
            roi_id=data.get("roi_id"),
            metadata=data.get("metadata", {}),
        )

    @classmethod
    def create(cls, roi) -> "Plot":
        """
        Create a plot from a region of interest (ROI).

        Args:
            roi: The ROI to create a plot from.

        Returns:
            Plot: A new plot instance.
        """
        # This is a placeholder implementation
        # In a real implementation, this would extract spectral data from the ROI
        return cls(
            name=f"Plot from {roi.name}",
            roi_id=roi.id,
            metadata={"source_roi": roi.name},
        )