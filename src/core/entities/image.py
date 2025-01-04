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


@dataclass(frozen=True)
class Image:
    """Data container representing an Image object in Varda"""

    raster: np.ndarray
    metadata: Metadata
    stretch: List[Stretch]
    band: List[Band]
    index: int

    def __eq__(self, other):
        return self.index == other.index
