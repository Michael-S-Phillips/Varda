"""
image.py
A core entity representing an image in varda.
"""

# standard library
from dataclasses import dataclass
from typing import List

# third party imports
import numpy as np

# local imports
from .band import Band
from .stretch import Stretch
from .metadata import Metadata
from .freehandROI import FreeHandROI


@dataclass(frozen=True)
class Image:
    """Immutable data container representing an Image object in Varda

    Attributes:
        raster (np.ndarray): a 3d array storing the raster (pixel) data of an image.
        metadata: The metadata associated with an image (See Metadata for details).
        stretch: A list of Stretch configurations for an image.
        band: A list of Band configurations for an image.
        index: A unique identifier for the image. Mainly to be used for comparisons.
    """

    raster: np.ndarray
    metadata: Metadata
    stretch: List[Stretch]
    band: List[Band]
    rois: List[FreeHandROI]
    index: int

    def __eq__(self, other):
        return self.index == other.index
