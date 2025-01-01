"""
image.py
A core entity representing an image in varda.
"""

# standard library
import logging
from dataclasses import dataclass, field
from typing import List

# third party imports
import numpy as np

# local imports
from .band import Band
from .stretch import Stretch
from .metadata import Metadata


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
