from dataclasses import dataclass, field
import numpy as np
from datetime import datetime
import uuid
from enum import Enum
from typing import List, Dict, Tuple, Optional, Any
import logging
import rasterio.transform

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
        points: Points defining the ROI in pixel coordinates [x, y]
        geoPoints: Points in geographic coordinates (if available) [lon, lat]
        color: RGBA color tuple (0-255 for each component)
        lineWidth: Width of the ROI outline
        fillOpacity: Opacity of the ROI fill (0.0 to 1.0)
        visible: Whether the ROI is currently visible
        creationTime: When the ROI was created
        description: User description of the ROI
        metadata: Additional metadata about the ROI
        arraySlice: Extracted image data within the ROI (optional)
        meanSpectrum: Mean spectral values within the ROI (optional)
        customData: Custom user-defined data associated with the ROI
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "New ROI"
    mode: ROIMode = ROIMode.FREEHAND
    sourceImageIndex: int = -1
    points: np.ndarray = field(default_factory=lambda: np.empty((0, 2)))
    geoPoints: Optional[np.ndarray] = None
    color: Tuple[int, int, int, int] = (255, 0, 0, 128)  # RGBA
    lineWidth: float = 1.0
    fillOpacity: float = 0.5
    visible: bool = True
    creationTime: datetime = field(default_factory=datetime.now)
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
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
        if not isinstance(self.color, tuple) or len(self.color) != 4:
            logger.warning(f"Invalid color {self.color}, using default")
            self.color = (255, 0, 0, 128)

    def get_pixel_points(self):
        """Get the ROI points in pixel coordinates"""
        return self.points

    def get_geo_points(self):
        """Get the ROI points in geographic coordinates"""
        return self.geoPoints

    def set_geo_points(self, geo_points):
        """Set the geographic coordinates for this ROI"""
        if isinstance(geo_points, list):
            geo_points = np.array(geo_points)
        self.geoPoints = geo_points

    def update_color(self, color):
        """Update the ROI color"""
        self.color = color

    def update_opacity(self, op):
        # update fill opacity (to hide roi)
        self.fillOpacity = op

    def update_properties(self, **kwargs):
        """Update multiple ROI properties at once"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                logger.warning(f"Unknown ROI property: {key}")

    def get_custom_value(self, column_name, default=None):
        """Get a custom data value by column name"""
        return self.customData.values.get(column_name, default)

    def set_custom_value(self, column_name, value):
        """Set a custom data value"""
        self.customData.values[column_name] = value

    def pixel_to_geo(self, transform):
        """
        Convert ROI pixel coordinates to geographic coordinates.

        Args:
            transform: A rasterio/affine transformation object

        Returns:
            Updated geo_points array
        """
        if self.points is None or transform is None:
            return None

        try:

            # Convert points using the geotransform
            geo_x, geo_y = [], []
            for i in range(len(self.points[0])):
                x, y = self.points[0][i], self.points[1][i]
                # Apply the transform
                geo_coord = rasterio.transform.xy(transform, y, x)
                geo_x.append(geo_coord[0])
                geo_y.append(geo_coord[1])

            self.geoPoints = np.array([geo_x, geo_y])
            return self.geoPoints
        except Exception as e:
            logger.error(f"Error converting to geo coordinates: {e}")
            return None

    def getBoundingBox(self):
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
        array_slice_list = None
        if self.arraySlice is not None:
            if isinstance(self.arraySlice, np.ndarray):
                array_slice_list = self.arraySlice.tolist()
            else:
                array_slice_list = self.arraySlice

        mean_spectrum_list = None
        if self.meanSpectrum is not None:
            if isinstance(self.meanSpectrum, np.ndarray):
                mean_spectrum_list = self.meanSpectrum.tolist()
            else:
                mean_spectrum_list = self.meanSpectrum

        return {
            "id": self.id,
            "name": self.name,
            "points": points_list,
            "geo_points": geo_points_list,
            "color": self.color,
            "line_width": self.lineWidth,
            "fill_opacity": self.fillOpacity,
            "visible": self.visible,
            "creation_time": self.creationTime.isoformat(),
            "description": self.description,
            "metadata": self.metadata,
            "array_slice": array_slice_list,
            "mean_spectrum": mean_spectrum_list,
            "custom_data": self.customData.serialize(),
        }

    @classmethod
    def deserialize(cls, data):
        """Create an ROI from a serialized dictionary"""
        # Convert lists back to numpy arrays
        points = np.array(data.get("points", []))

        geo_points = data.get("geo_points")
        if geo_points is not None:
            geo_points = np.array(geo_points)

        # Handle DateTime conversion
        creation_time = data.get("creation_time")
        if isinstance(creation_time, str):
            try:
                creation_time = datetime.fromisoformat(creation_time)
            except ValueError:
                creation_time = datetime.now()
        else:
            creation_time = datetime.now()

        # Handle array_slice and mean_spectrum
        array_slice = data.get("array_slice")
        if array_slice is not None:
            array_slice = np.array(array_slice)

        mean_spectrum = data.get("mean_spectrum")
        if mean_spectrum is not None:
            mean_spectrum = np.array(mean_spectrum)

        # Handle custom data
        custom_data = ROICustomData.deserialize(data.get("custom_data", {}))

        # Ensure image_indices is a list
        image_indices = data.get("image_indices", [])
        if not isinstance(image_indices, list):
            image_indices = [image_indices] if image_indices is not None else []

        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data.get("name", "ROI"),
            points=points,
            geoPoints=geo_points,
            color=data.get("color", (255, 0, 0, 128)),
            lineWidth=data.get("line_width", 2.0),
            fillOpacity=data.get("fill_opacity", 0.5),
            visible=data.get("visible", True),
            creationTime=creation_time,
            description=data.get("description", ""),
            metadata=data.get("metadata", {}),
            arraySlice=array_slice,
            meanSpectrum=mean_spectrum,
            customData=custom_data,
        )

    def clone(self):
        """Create a deep copy of the ROI"""
        return ROI.deserialize(self.serialize())

    def __str__(self):
        return f"ROI '{self.name}' ({self.id}) with {len(self.points)} points"
