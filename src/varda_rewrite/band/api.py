from typing import Protocol

from varda_rewrite.image.api import Wavelength


class DisplayBandConfiguration(Protocol):
    """A 3-channel Band configuration, generally to represent mappings to RGB channels."""

    r: Wavelength
    g: Wavelength
    b: Wavelength
