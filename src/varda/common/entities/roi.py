from dataclasses import dataclass, field
import numpy as np
from datetime import datetime
import uuid
from enum import Enum
from typing import Dict, Optional, Any
import logging

import geopandas as gpd
from PyQt6.QtGui import QColor

logger = logging.getLogger(__name__)


class ROIMode(Enum):
    """Enum to define different ROI drawing modes"""

    FREEHAND = 0
    RECTANGLE = 1
    ELLIPSE = 2
    POLYGON = 3  # Click-by-click polygon


@dataclass
class ROICustomData:
    """Stores custom data for an ROI"""

    values: Dict[str, Any] = field(default_factory=dict)

    def serialize(self):
        """Serialize custom data for storage"""
        # Convert any non-serializable values to strings
        serialized = {}
        for key, value in self.values.items():
            if isinstance(value, np.ndarray):
                serialized[key] = value.tolist()
            else:
                serialized[key] = value
        return serialized

    @classmethod
    def deserialize(cls, data):
        """Deserialize custom data from storage"""
        custom_data = cls()
        custom_data.values = data
        return custom_data


@dataclass
class ROI:
    """Enhanced data container for a region of interest in an image.

    Attributes:
        id: Unique identifier for the ROI
        name: User-friendly name for the ROI
        mode: Drawing mode for the ROI (e.g., freehand, rectangle)
        sourceImageIndex: Index of the source image this ROI was created from
        points: Points defining the ROI in pixel coordinates [x, y]
        geoPoints: Points in geographic coordinates (if available) [lon, lat]
        color: The ROI color in RGBA 0-255 format, in a QColor object
        visible: Whether the ROI is currently visible
        creationTime: When the ROI was created
        description: User description of the ROI
        arraySlice: Extracted image data within the ROI (optional)
        meanSpectrum: Mean spectral values within the ROI (optional)
        customData: Custom user-defined data associated with the ROI
    """

    gdf: Optional[gpd.GeoDataFrame] = field(default_factory=lambda: gpd.GeoDataFrame())
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Unnamed ROI"
    mode: ROIMode = ROIMode.FREEHAND
    sourceImageIndex: int = -1
    points: np.ndarray = field(default_factory=lambda: np.empty((0, 2)))
    geoPoints: Optional[np.ndarray] = None
    color: QColor = field(default_factory=lambda: QColor(255, 0, 0, 128))
    visible: bool = True
    creationTime: datetime = field(default_factory=datetime.now)
    description: str = "No description"
    arraySlice: Optional[np.ndarray] = None
    meanSpectrum: Optional[np.ndarray] = None
    customData: ROICustomData = field(default_factory=ROICustomData)

    def __post_init__(self):
        """Validate and initialize the ROI after creation"""
        # Ensure points is a numpy array
        if not isinstance(self.points, np.ndarray):
            if isinstance(self.points, list):
                self.points = np.array(self.points)
            else:
                logger.warning(
                    f"Converting invalid points type {type(self.points)} to empty array"
                )
                self.points = np.array([])

        # Same for geo_points
        if self.geoPoints is not None and not isinstance(self.geoPoints, np.ndarray):
            if isinstance(self.geoPoints, list):
                self.geoPoints = np.array(self.geoPoints)
            else:
                logger.warning(
                    f"Converting invalid geo_points type {type(self.geoPoints)} to None"
                )
                self.geoPoints = None

        # Ensure color is a valid RGBA tuple
        if not isinstance(self.color, QColor):
            logger.warning(f"Invalid color {self.color}, using default")
            self.color = QColor(255, 0, 0, 128)  # Default red with 50% opacity

    def updateProperties(self, **kwargs):
        """Update multiple ROI properties at once"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                logger.warning(f"Unknown ROI property: {key}")

    def getCustomValue(self, column_name, default=None):
        """Get a custom data value by column name"""
        return self.customData.values.get(column_name, default)

    def setCustomValue(self, column_name, value):
        """Set a custom data value"""
        self.customData.values[column_name] = value

    def getBounds(self):
        """Calculate the bounding box of the ROI points"""
        if len(self.points) == 0:
            return 0, 0, 0, 0
        min_x, min_y = self.points.min(axis=0)
        max_x, max_y = self.points.max(axis=0)
        return min_x, min_y, max_x, max_y

    def serialize(self):
        """Convert the ROI to a serializable dictionary"""
        # Convert numpy arrays to lists for serialization
        points_list = (
            self.points.tolist() if isinstance(self.points, np.ndarray) else []
        )
        geo_points_list = (
            self.geoPoints.tolist() if isinstance(self.geoPoints, np.ndarray) else None
        )

        # Convert array_slice and mean_spectrum to lists if they exist
        array_slice_list = array_slice_list = (
            self.arraySlice.tolist() if self.arraySlice is not None else None
        )

        mean_spectrum_list = (
            self.meanSpectrum.tolist() if self.meanSpectrum is not None else None
        )

        # convert color to tuple
        colorTuple = (
            self.color.red(),
            self.color.green(),
            self.color.blue(),
            self.color.alpha(),
        )
        return {
            "id": self.id,
            "name": self.name,
            "mode": self.mode.name,
            "sourceImageIndex": self.sourceImageIndex,
            "points": points_list,
            "geoPoints": geo_points_list,
            "color": colorTuple,
            "visible": self.visible,
            "creationTime": self.creationTime.isoformat(),
            "description": self.description,
            "arraySlice": array_slice_list,
            "meanSpectrum": mean_spectrum_list,
            "customData": self.customData.serialize(),
        }

    @classmethod
    def deserialize(cls, data):
        """Create an ROI from a serialized dictionary"""
        inputKwargs = {}

        if data.get("id"):
            inputKwargs["id"] = data["id"]
        if data.get("name"):
            inputKwargs["name"] = data["name"]
        if data.get("mode"):
            inputKwargs["mode"] = ROIMode[data["mode"]]
        if data.get("sourceImageIndex") is not None:
            inputKwargs["sourceImageIndex"] = data["sourceImageIndex"]

        points = data.get("points")
        if points is not None:
            inputKwargs["points"] = np.array(points)

        geo_points = data.get("geoPoints")
        if geo_points is not None:
            inputKwargs["geoPoints"] = np.array(geo_points)

        creationTime = data.get("creationTime")
        if creationTime:
            inputKwargs["creationTime"] = datetime.fromisoformat(creationTime)

        array_slice = data.get("arraySlice")
        if array_slice is not None:
            inputKwargs["arraySlice"] = np.array(array_slice)

        mean_spectrum = data.get("meanSpectrum")
        if mean_spectrum is not None:
            inputKwargs["meanSpectrum"] = np.array(mean_spectrum)

        color = data.get("color")
        if color is not None:
            inputKwargs["color"] = QColor(*color)

        visible = data.get("visible")
        if visible is not None:
            inputKwargs["visible"] = visible

        description = data.get("description")
        if description is not None:
            inputKwargs["description"] = description

        custom_data = data.get("customData")
        if custom_data is not None:
            inputKwargs["customData"] = ROICustomData.deserialize(custom_data)

        return cls(**inputKwargs)

    def clone(self):
        """Create a deep copy of the ROI"""
        return ROI.deserialize(self.serialize())

    def __str__(self):
        return f"ROI '{self.name}' ({self.id}) with {len(self.points)} points"
