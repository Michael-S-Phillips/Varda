"""Loaded images on the find-data map: as a basemap (its display bands,
reprojected to the map's projection) or as a search area (its bounds in
longitude and latitude)."""

from __future__ import annotations

import math

import numpy as np
from affine import Affine
from pyproj import CRS
from rasterio.transform import array_bounds, from_bounds
from rasterio.warp import Resampling, reproject, transform_bounds

from varda.catalogs.bodies import bodyOf, geographicCrs
from varda.common.entities import VardaRaster
from varda.workspaces.find_data.projection import Projector
from varda.workspaces.mosaic.views import displayBands, downsampled, toRgba

BASEMAP_PIXELS = 1500

Bounds = tuple[float, float, float, float]  # west, south, east, north


def imageBody(image: VardaRaster) -> str | None:
    """The body a georeferenced image shows (None without a CRS)."""
    if image.crs is None:
        return None
    return bodyOf(CRS.from_user_input(image.crs))  # a rasterio CRS or a PROJ string


def imageBounds(image: VardaRaster, body: str) -> Bounds:
    """The image's bounds in the body's longitude and latitude."""
    bounds = array_bounds(image.height, image.width, image.transform)
    return tuple(transform_bounds(image.crs, geographicCrs(body), *bounds))


def basemap(image: VardaRaster, projector: Projector) -> tuple[np.ndarray, Bounds]:
    """The image's display bands as RGBA (rows north to south) in the map's
    projection, and their bounds in map coordinates. A polar view gets the
    part of the image in its hemisphere."""
    bounds = projector.mapBounds(imageBounds(image, projector.body))
    if bounds is None:
        raise ValueError("The image is in the other hemisphere.")
    west, south, east, north = bounds
    cube, step = downsampled(image, displayBands(image), BASEMAP_PIXELS)
    transform = image.transform * Affine.scale(step)
    scale = BASEMAP_PIXELS / max(east - west, north - south)
    width = max(1, math.ceil((east - west) * scale))
    height = max(1, math.ceil((north - south) * scale))
    destination = from_bounds(west, south, east, north, width, height)
    out = np.full((cube.shape[2], height, width), np.nan, np.float32)
    reproject(
        source=cube.transpose(2, 0, 1).astype(np.float32),
        destination=out,
        src_transform=transform,
        src_crs=image.crs,
        dst_transform=destination,
        dst_crs=projector.crs,
        resampling=Resampling.nearest,
        src_nodata=np.nan,
        dst_nodata=np.nan,
    )
    return toRgba(out.transpose(1, 2, 0)), bounds
