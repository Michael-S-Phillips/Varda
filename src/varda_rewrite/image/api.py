from typing import Protocol
from dataclasses import dataclass


class Wavelength(Protocol):
    name: str
    index: int
    value: float
    owningImageId: str


class RasterData(Protocol):
    def __array__(self): ...


@dataclass
class Image(Protocol):
    id: str
    raster: RasterData
