from dataclasses import dataclass
from typing import List

from varda_rewrite.image.api import Wavelength


@dataclass
class Band:
    """Immutable data container representing a Band configuration for an image."""

    name: str
    r: int
    g: int
    b: int


@dataclass
class DisplayBandConfiguration:
    """A 3-channel Band configuration, generally to represent RGB channels."""

    r: Wavelength
    g: Wavelength
    b: Wavelength


@dataclass
class BandConfiguration:
    """A Band configuration with an arbitrary number of channels."""

    bands: List[Band]
