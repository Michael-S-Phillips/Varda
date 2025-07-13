"""
image.py
A core entity representing an image in varda.
"""

# standard library
from dataclasses import dataclass, field
from typing import List

# third party imports
import numpy as np
from PyQt6.QtWidgets import QWidget

# local imports
from .band import Band
from .stretch import Stretch
from .metadata import Metadata
from .roi import ROI
from .plot import Plot


@dataclass
class Image:
    """data container representing an Image object in Varda

    Attributes:
        raster (np.ndarray): a 3d array storing the raster (pixel) data of an image.
        metadata: The metadata associated with an image (See Metadata for details).
        stretch: A list of Stretch configurations for an image.
        band: A list of Band configurations for an image.
        index: A unique identifier for the image. Mainly to be used for comparisons.
    """

    raster: np.ndarray
    metadata: Metadata = None
    stretch: List[Stretch] = field(default_factory=list)
    band: List[Band] = field(default_factory=list)
    rois: List[ROI] = field(default_factory=list)
    plots: List[Plot] = field(default_factory=list)
    ROIview: QWidget = None
    index: int = -1

    def __post_init__(self):
        # We do not want to allow modification of the raster data directly I think.
        self.raster.setflags(write=False)

    def height(self):
        return self.raster.shape[0]

    def width(self):
        return self.raster.shape[1]

    def __eq__(self, other):
        return self.index == other.index
