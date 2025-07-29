"""
Domain entity for image metadata in Varda.

This module defines the Metadata class, which represents metadata for a hyperspectral image.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any, List, Union

import numpy as np


@dataclass
class Metadata:
    """
    Data representation of image metadata.
    
    Metadata includes information about the image dimensions, data type,
    geospatial information, and other properties.
    """

    # Basic metadata
    width: int = 0
    height: int = 0
    bandCount: int = 0
    dtype: str = "float32"
    filePath: Optional[Path] = None
    name: Optional[str] = None
    
    # Geospatial metadata
    resolution: Optional[tuple] = None
    crs: Optional[str] = None
    transform: Optional[Any] = None
    geoReferencer: Optional[Any] = None
    
    # Spectral metadata
    wavelengths: Optional[np.ndarray] = None
    wavelengths_type: Optional[type] = None
    wavelength_units: Optional[str] = None
    
    # Default visualization
    defaultBand: Optional[Any] = None
    dataIgnore: float = 0.0
    
    # Additional metadata
    extraMetadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def hasGeospatialData(self) -> bool:
        """Check if the metadata contains geospatial information."""
        return self.crs is not None and self.transform is not None
    
    def serialize(self) -> Dict[str, Any]:
        """
        Serialize the metadata into a JSON-compatible dictionary.

        Returns:
            Dict[str, Any]: The serialized metadata.
        """
        # Convert numpy arrays to lists for serialization
        wavelengths = None
        if self.wavelengths is not None:
            if self.wavelengths_type == str:
                wavelengths = self.wavelengths.tolist()
            else:
                wavelengths = [float(w) for w in self.wavelengths]
        
        # Convert Path to string
        file_path = str(self.filePath) if self.filePath else None
        
        # Serialize the default band if it exists
        default_band = None
        if self.defaultBand:
            default_band = self.defaultBand.serialize()
        
        # Build the serialized dictionary
        result = {
            "width": self.width,
            "height": self.height,
            "bandCount": self.bandCount,
            "dtype": self.dtype,
            "filePath": file_path,
            "name": self.name,
            "resolution": self.resolution,
            "crs": self.crs,
            "transform": self.transform,
            "wavelengths": wavelengths,
            "wavelengths_type": str(self.wavelengths_type) if self.wavelengths_type else None,
            "wavelength_units": self.wavelength_units,
            "defaultBand": default_band,
            "dataIgnore": self.dataIgnore,
            "extraMetadata": self.extraMetadata,
        }
        
        return result
    
    @classmethod
    def deserialize(cls, data: Dict[str, Any]) -> "Metadata":
        """
        Create a Metadata instance from serialized data.

        Args:
            data: The serialized metadata.

        Returns:
            Metadata: The deserialized Metadata instance.
        """
        from varda.common.domain.band import Band
        
        # Convert string to Path
        file_path = Path(data["filePath"]) if data.get("filePath") else None
        
        # Convert wavelengths back to numpy array
        wavelengths = data.get("wavelengths")
        wavelengths_type_str = data.get("wavelengths_type")
        wavelengths_type = None
        
        if wavelengths_type_str:
            if wavelengths_type_str == "<class 'str'>":
                wavelengths_type = str
                if wavelengths:
                    wavelengths = np.array(wavelengths, dtype="U50")
            elif wavelengths_type_str == "<class 'float'>":
                wavelengths_type = float
                if wavelengths:
                    wavelengths = np.array(wavelengths, dtype=float)
            elif wavelengths_type_str == "<class 'int'>":
                wavelengths_type = int
                if wavelengths:
                    wavelengths = np.array(wavelengths, dtype=int)
        
        # Deserialize the default band if it exists
        default_band = None
        if data.get("defaultBand"):
            default_band = Band.deserialize(data["defaultBand"])
        
        # Create the Metadata instance
        return cls(
            width=data.get("width", 0),
            height=data.get("height", 0),
            bandCount=data.get("bandCount", 0),
            dtype=data.get("dtype", "float32"),
            filePath=file_path,
            name=data.get("name"),
            resolution=data.get("resolution"),
            crs=data.get("crs"),
            transform=data.get("transform"),
            wavelengths=wavelengths,
            wavelengths_type=wavelengths_type,
            wavelength_units=data.get("wavelength_units"),
            defaultBand=default_band,
            dataIgnore=data.get("dataIgnore", 0.0),
            extraMetadata=data.get("extraMetadata", {}),
        )