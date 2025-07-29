"""
Domain entity for an image in Varda.

This module defines the Image class, which represents a hyperspectral image.
"""
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

import numpy as np

from varda.common.domain.metadata import Metadata
from varda.common.domain.band import Band
from varda.common.domain.stretch import Stretch
from varda.common.domain.plot import Plot


@dataclass
class Image:
    """
    Data representation of a hyperspectral image.
    
    An image consists of raster data (the actual pixel values), metadata,
    and various configurations for visualization (bands, stretches, plots).
    """

    raster: Optional[np.ndarray]
    metadata: Metadata
    stretch: List[Stretch] = field(default_factory=list)
    band: List[Band] = field(default_factory=list)
    plots: List[Plot] = field(default_factory=list)
    index: int = -1

    def serialize(self) -> Dict[str, Any]:
        """
        Serialize the image data into a JSON-compatible dictionary.
        
        Note that the raster data is not serialized, as it's typically
        loaded separately from the image file.

        Returns:
            Dict[str, Any]: The serialized image data.
        """
        return {
            "metadata": self.metadata.serialize(),
            "stretch": [s.serialize() for s in self.stretch],
            "band": [b.serialize() for b in self.band],
            "plots": [p.serialize() for p in self.plots],
            "index": self.index,
        }

    @classmethod
    def deserialize(cls, data: Dict[str, Any]) -> "Image":
        """
        Create an Image instance from serialized data.

        Args:
            data: The serialized image data.

        Returns:
            Image: The deserialized Image instance.
        """
        metadata = Metadata.deserialize(data.get("metadata", {}))
        stretches = [Stretch.deserialize(s) for s in data.get("stretch", [])]
        bands = [Band.deserialize(b) for b in data.get("band", [])]
        plots = [Plot.deserialize(p) for p in data.get("plots", [])]
        
        return cls(
            raster=None,  # Raster data is loaded separately
            metadata=metadata,
            stretch=stretches,
            band=bands,
            plots=plots,
            index=data.get("index", -1),
        )