"""
This module defines the ImageModel class, which serves as the base model for images
in the Varda application.
It provides a consistent interface for image data and includes signals and slots
for communication between the image model and other components.
"""

# standard library
import logging
from dataclasses import dataclass, field
from typing import List

# third party imports
import numpy as np

# local imports

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Image:
    _raster: np.ndarray
    _metadata: Metadata
    _stretch: List[Stretch] = field(default_factory=list)
    _band: List[Band] = field(default_factory=list)
    _index: int = -1

    @property
    def raster(self):
        return self._raster

    @property
    def metadata(self):
        return self._metadata

    @property
    def stretch(self):
        return self._stretch

    @property
    def band(self):
        return self._band
