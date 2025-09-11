from uuid import uuid4
from typing import Union

import numpy as np
import rasterio
from affine import Affine
from pydantic.types import UUID4
from pyproj import CRS, Transformer
from pydantic import BaseModel, model_validator
from numpydantic import NDArray, Shape

from varda_rewrite.project_io.api import RegisterStore


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

    def __post_model_init__(self):
        self.toGeo = Transformer.from_crs(
            self.crs, self.crs.geodetic_crs, always_xy=True
        )

    def transformPixelToGeoCoord(self, px: int, py: int) -> tuple[float, float]:
        """Transform pixel coordinates to geospatial coordinates.

        Args:
            image (Image): The image object containing geospatial metadata.
            px (int): The pixel x-coordinate.
            py (int): The pixel y-coordinate.

        Returns:
            tuple[float, float]: The transformed geospatial coordinates (longitude, latitude).
        """

        # Convert pixel coordinates to map coordinates (x, y)
        mx, my = rasterio.transform.xy(self.transform, px, py)
        # Transform map coordinates to geographic coordinates
        lon, lat = self.toGeo.transform(mx, my)
        return lon, lat


class _Image(BaseModel):
    name: str
    uid: str = str(uuid4())
    raster: NDArray[Shape["*, *, *"], np.float64]  # type: ignore
    geo: _GeoInfo | None = None
    wavelengths: list[_Wavelength]

    # adding this tells numpy how to "convert" this object to an array, so it can be used directly in calculations
    def __array__(self):
        return self.raster

    # this lets us use the list indexing syntax (e.g. img[:, :, 1]) to access the raster data
    def __getitem__(self, key):
        return self.raster[key]


class ImageStore:

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

    def serialize(self): ...

    def deserialize(self): ...
