from typing import Union

import numpy as np
from affine import Affine
from pyproj import CRS
from pydantic import BaseModel, model_validator
from numpydantic import NDArray, Shape


class _Wavelength(BaseModel):
    name: str
    index: int
    data: NDArray[Shape["*, *"], np.float64]  # type: ignore


class _GeoInfo(BaseModel):
    crs: CRS
    transform: Affine

    model_config = {"arbitrary_types_allowed": True}

    @model_validator(mode="after")
    def validate_crs(self):
        if self.crs.geodetic_crs is None:
            raise ValueError("CRS has no geodetic CRS")


class _Image(BaseModel):
    name: str
    raster: NDArray[Shape["*, *, *"], np.float64]  # type: ignore
    geo: _GeoInfo | None = None
    wavelengths: list[_Wavelength]

    # Im wondering if we should remove the "raster" attribute and just make the Image useable like an array,
    # that also has extra metadata attached to it lol.

    # adding this tells numpy how to "convert" this object to an array, so it can be used directly in calculations
    def __array__(self):
        return self.raster


class ImageStorage:
    def __init__(self):
        self.images: dict[str, _Image] = {}

    def addImage(self, image: _Image):
        self.images[image.name] = image

    def getImage(self, name: str) -> Union[_Image, None]:
        return self.images.get(name, None)

    def removeImage(self, name: str):
        del self.images[name]

    def reset(self):
        self.images = {}

    def save(self): ...

    def load(self, data): ...
