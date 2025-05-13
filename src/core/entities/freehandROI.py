from dataclasses import dataclass, field
import numpy as np
from datetime import datetime
import uuid
from typing import List, Dict, Tuple, Optional, Any
import logging

logger = logging.getLogger(__name__)

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
class FreehandROI:
    """Enhanced data container for a region of interest in an image.
    
    Attributes:
        id: Unique identifier for the ROI
        name: User-friendly name for the ROI
        points: Points defining the ROI in pixel coordinates [x, y]
        geo_points: Points in geographic coordinates (if available) [lon, lat]
        image_indices: List of image indices this ROI is associated with
        color: RGBA color tuple (0-255 for each component)
        line_width: Width of the ROI outline
        fill_opacity: Opacity of the ROI fill (0.0 to 1.0)
        visible: Whether the ROI is currently visible
        creation_time: When the ROI was created
        description: User description of the ROI
        metadata: Additional metadata about the ROI
        array_slice: Extracted image data within the ROI (optional)
        mean_spectrum: Mean spectral values within the ROI (optional)
        custom_data: Custom user-defined data associated with the ROI
    """
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "New ROI"
    points: np.ndarray = field(default_factory=lambda: np.array([]))
    geo_points: Optional[np.ndarray] = None
    image_indices: List[int] = field(default_factory=list)  # This should be a list by default
    color: Tuple[int, int, int, int] = (255, 0, 0, 128)  # RGBA
    line_width: float = 2.0
    fill_opacity: float = 0.5
    visible: bool = True
    creation_time: datetime = field(default_factory=datetime.now)
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    array_slice: Optional[np.ndarray] = None
    mean_spectrum: Optional[np.ndarray] = None
    custom_data: ROICustomData = field(default_factory=ROICustomData)
    
    def __post_init__(self):
        """Validate and initialize the ROI after creation"""
        # Ensure points is a numpy array
        if not isinstance(self.points, np.ndarray):
            if isinstance(self.points, list):
                self.points = np.array(self.points)
            else:
                logger.warning(f"Converting invalid points type {type(self.points)} to empty array")
                self.points = np.array([])
        
        # Same for geo_points
        if self.geo_points is not None and not isinstance(self.geo_points, np.ndarray):
            if isinstance(self.geo_points, list):
                self.geo_points = np.array(self.geo_points)
            else:
                logger.warning(f"Converting invalid geo_points type {type(self.geo_points)} to None")
                self.geo_points = None
                
        # Ensure color is a valid RGBA tuple
        if not isinstance(self.color, tuple) or len(self.color) != 4:
            logger.warning(f"Invalid color {self.color}, using default")
            self.color = (255, 0, 0, 128)
            
        # Ensure image_indices is a list
        if not isinstance(self.image_indices, list):
            logger.warning(f"Converting image_indices from {type(self.image_indices)} to list")
            if self.image_indices is None:
                self.image_indices = []
            else:
                self.image_indices = [self.image_indices]
    
    def get_pixel_points(self):
        """Get the ROI points in pixel coordinates"""
        return self.points
    
    def get_geo_points(self):
        """Get the ROI points in geographic coordinates"""
        return self.geo_points
    
    def set_geo_points(self, geo_points):
        """Set the geographic coordinates for this ROI"""
        if isinstance(geo_points, list):
            geo_points = np.array(geo_points)
        self.geo_points = geo_points
    
    def add_image_index(self, image_index):
        """Associate this ROI with an image index"""
        if image_index not in self.image_indices:
            self.image_indices.append(image_index)
    
    def remove_image_index(self, image_index):
        """Remove association with an image index"""
        if image_index in self.image_indices:
            self.image_indices.remove(image_index)
    
    def update_color(self, color):
        """Update the ROI color"""
        self.color = color
    
    def update_properties(self, **kwargs):
        """Update multiple ROI properties at once"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                logger.warning(f"Unknown ROI property: {key}")
    
    def get_custom_value(self, column_name, default=None):
        """Get a custom data value by column name"""
        return self.custom_data.values.get(column_name, default)
    
    def set_custom_value(self, column_name, value):
        """Set a custom data value"""
        self.custom_data.values[column_name] = value
    
    def serialize(self):
        """Convert the ROI to a serializable dictionary"""
        # Convert numpy arrays to lists for serialization
        points_list = self.points.tolist() if isinstance(self.points, np.ndarray) else []
        geo_points_list = self.geo_points.tolist() if isinstance(self.geo_points, np.ndarray) else None
        
        # Convert array_slice and mean_spectrum to lists if they exist
        array_slice_list = None
        if self.array_slice is not None:
            if isinstance(self.array_slice, np.ndarray):
                array_slice_list = self.array_slice.tolist()
            else:
                array_slice_list = self.array_slice
                
        mean_spectrum_list = None
        if self.mean_spectrum is not None:
            if isinstance(self.mean_spectrum, np.ndarray):
                mean_spectrum_list = self.mean_spectrum.tolist()
            else:
                mean_spectrum_list = self.mean_spectrum
        
        return {
            "id": self.id,
            "name": self.name,
            "points": points_list,
            "geo_points": geo_points_list,
            "image_indices": self.image_indices,
            "color": self.color,
            "line_width": self.line_width,
            "fill_opacity": self.fill_opacity,
            "visible": self.visible,
            "creation_time": self.creation_time.isoformat(),
            "description": self.description,
            "metadata": self.metadata,
            "array_slice": array_slice_list,
            "mean_spectrum": mean_spectrum_list,
            "custom_data": self.custom_data.serialize()
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
            geo_points=geo_points,
            image_indices=image_indices,
            color=data.get("color", (255, 0, 0, 128)),
            line_width=data.get("line_width", 2.0),
            fill_opacity=data.get("fill_opacity", 0.5),
            visible=data.get("visible", True),
            creation_time=creation_time,
            description=data.get("description", ""),
            metadata=data.get("metadata", {}),
            array_slice=array_slice,
            mean_spectrum=mean_spectrum,
            custom_data=custom_data
        )
    
    def __str__(self):
        return f"ROI '{self.name}' ({self.id}) with {len(self.points)} points"