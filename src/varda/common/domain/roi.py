"""
Domain entity for regions of interest (ROIs) in Varda.

This module defines the ROI class, which represents a region of interest
in a hyperspectral image.
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
from uuid import uuid4

import numpy as np


@dataclass
class ROI:
    """
    Data representation of a region of interest (ROI).
    
    An ROI defines a region in an image that is of interest for analysis.
    It includes the geometry of the region, as well as metadata about the ROI.
    """

    name: str
    geometry: Any  # This could be a polygon, rectangle, etc.
    image_indices: List[int]
    id: str = field(default_factory=lambda: str(uuid4()))
    color: str = "#FF0000"  # Default to red
    visible: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

    def serialize(self) -> Dict[str, Any]:
        """
        Serialize the ROI into a JSON-compatible dictionary.

        Returns:
            Dict[str, Any]: The serialized ROI.
        """
        # Convert geometry to a serializable format
        # This is a placeholder implementation
        # In a real implementation, this would depend on the type of geometry
        geometry_data = None
        if self.geometry is not None:
            if hasattr(self.geometry, "serialize"):
                geometry_data = self.geometry.serialize()
            elif hasattr(self.geometry, "tolist"):
                geometry_data = self.geometry.tolist()
            else:
                geometry_data = str(self.geometry)
        
        return {
            "name": self.name,
            "geometry": geometry_data,
            "image_indices": self.image_indices,
            "id": self.id,
            "color": self.color,
            "visible": self.visible,
            "metadata": self.metadata,
        }

    @classmethod
    def deserialize(cls, data: Dict[str, Any]) -> "ROI":
        """
        Create an ROI instance from serialized data.

        Args:
            data: The serialized ROI.

        Returns:
            ROI: The deserialized ROI instance.
        """
        # Convert serialized geometry back to the appropriate type
        # This is a placeholder implementation
        # In a real implementation, this would depend on the type of geometry
        geometry = data.get("geometry")
        
        return cls(
            name=data.get("name", ""),
            geometry=geometry,
            image_indices=data.get("image_indices", []),
            id=data.get("id", str(uuid4())),
            color=data.get("color", "#FF0000"),
            visible=data.get("visible", True),
            metadata=data.get("metadata", {}),
        )

    def get_bounds(self) -> Tuple[float, float, float, float]:
        """
        Get the bounding box of the ROI.

        Returns:
            Tuple[float, float, float, float]: The bounding box as (x_min, y_min, x_max, y_max).
        """
        # This is a placeholder implementation
        # In a real implementation, this would depend on the type of geometry
        if self.geometry is None:
            return (0.0, 0.0, 0.0, 0.0)
        
        if hasattr(self.geometry, "boundingRect"):
            rect = self.geometry.boundingRect()
            return (rect.left(), rect.top(), rect.right(), rect.bottom())
        
        return (0.0, 0.0, 0.0, 0.0)

    def contains_point(self, x: float, y: float) -> bool:
        """
        Check if the ROI contains a point.

        Args:
            x: The x-coordinate of the point.
            y: The y-coordinate of the point.

        Returns:
            bool: True if the ROI contains the point, False otherwise.
        """
        # This is a placeholder implementation
        # In a real implementation, this would depend on the type of geometry
        if self.geometry is None:
            return False
        
        if hasattr(self.geometry, "contains"):
            return self.geometry.contains(x, y)
        
        return False