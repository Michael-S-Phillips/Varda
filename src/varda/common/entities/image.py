"""
image.py
A core entity representing an image in varda.
"""

# standard library
from dataclasses import dataclass, field
from typing import List
import uuid
import logging

# third party imports
import numpy as np
from PyQt6.QtWidgets import QWidget

# local imports
from .band import Band
from .stretch import Stretch
from .metadata import Metadata
from .roi import ROI
from .plot import Plot

logger = logging.getLogger(__name__)


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

    @property
    def height(self):
        return self.raster.shape[0]

    @property
    def width(self):
        return self.raster.shape[1]

    def getRasterFromBand(self, band: Band):
        """Get a subset of the raster data for RGB display.

        Creates a 3-band subset of the raster data based on the RGB channels
        defined in the selected band configuration.

        Returns:
            np.ndarray: Array  with shape (height, width, 3) for RGB display
        """

        # Get the RGB bands from the raster data
        rgbData = self.raster[:, :, [band.r, band.g, band.b]]

        # Handle any out-of-range values
        # if np.isnan(rgbData).any():
        #     logger.warning(
        #         f"NaN values found in raster data for bands {[band.r, band.g, band.b]}"
        #     )
        #     rgbData = np.nan_to_num(rgbData)

        return rgbData

    def __eq__(self, other):
        return self.index == other.index
