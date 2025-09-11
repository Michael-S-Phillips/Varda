from typing import Protocol
from dataclasses import dataclass

from affine import Affine
from pyproj import CRS

from .domain import ImageStore


class GeoInfo(Protocol):
    crs: CRS
    transform: Affine

    def transformPixelToGeoCoord(self, px: int, py: int) -> tuple[float, float]: ...


class Wavelength(Protocol):
    name: str
    index: int
    value: float
    owningImageId: str


class Image(Protocol):
    name: str
    raster: NDArray[Shape["*, *, *"], np.float64]  # type: ignore
    wavelengths: list[Wavelength]
    geo: GeoInfo | None
    uid: str
