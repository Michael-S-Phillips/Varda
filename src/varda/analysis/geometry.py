"""Geometry: resample (resize), rotate or flip, and subset an image, keeping
its georeferencing right (the transform follows the pixels) and, for a
subset, its band metadata."""

from __future__ import annotations


import numpy as np
from affine import Affine
from scipy import ndimage

from varda.analysis.analysis import Analysis, ProgressCallback
from varda.analysis.bandwise import fillGaps, readBand
from varda.analysis.rasters import sameBandsRaster
from varda.common.entities import VardaRaster
from varda.common.parameter import (
    LabeledEnum,
    EnumParameter,
    FloatParameter,
    IntParameter,
    StringParameter,
    parsePositions,
)
from varda.common.spectral_axis import BAND_METADATA_KEYS, parseEnviList
from varda.image_loading.data_sources.array_data_source import ArrayDataSource

CATEGORY = "Geometry"


def readCubeWithGaps(image: VardaRaster) -> np.ndarray:
    """The whole image as float32, NaN where it's no-data."""
    cube = np.ma.filled(np.ma.asarray(image.getData(), dtype=np.float32), np.nan)
    if image.nodata is not None:
        cube[cube == image.nodata] = np.nan
    return cube


class Interpolation(LabeledEnum):
    NEAREST = "Nearest neighbor"
    BILINEAR = "Bilinear"
    CUBIC = "Cubic"


class ResampleAnalysis(Analysis):
    analysisId = "resample"
    name = "Resample (Resize)"
    category = CATEGORY
    description = (
        "Change the number of pixels: a factor above 1 enlarges, below 1 "
        "shrinks (e.g. 0.5 halves each side). Nearest neighbor keeps the "
        "original values (use it for class maps); bilinear and cubic "
        "interpolate. The georeferencing is updated to the new pixel size."
    )

    factor = FloatParameter(
        "Scale Factor",
        0.5,
        range=(0.01, 20.0),
        description="New size over old size, both sides",
        step=0.05,
    )
    interpolation = EnumParameter(
        "Interpolation", Interpolation, Interpolation.BILINEAR
    )

    def run(self, image: VardaRaster, reportProgress: ProgressCallback) -> VardaRaster:
        factor = float(self.factor.value)
        rows = max(int(round(image.height * factor)), 1)
        cols = max(int(round(image.width * factor)), 1)
        zoom = (rows / image.height, cols / image.width)
        order = {
            Interpolation.NEAREST: 0,
            Interpolation.BILINEAR: 1,
            Interpolation.CUBIC: 3,
        }[self.interpolation.value]
        output = np.empty((rows, cols, image.bandCount), np.float32)
        for index in range(image.bandCount):
            reportProgress(int(100 * index / image.bandCount), f"band {index + 1}")
            filled, missing = fillGaps(readBand(image, index))
            # grid_mode: pixels are areas, so the corners stay where they were
            band = ndimage.zoom(
                filled, zoom, order=order, mode="nearest", grid_mode=True
            )
            gaps = ndimage.zoom(missing, zoom, order=0, mode="nearest", grid_mode=True)
            output[:, :, index] = np.where(gaps, np.nan, band)
        transform = image.transform * Affine.scale(
            image.width / cols, image.height / rows
        )
        return sameBandsRaster(
            image,
            output,
            name=f"{image.name} ×{factor:g}",
            description=f"{image.name} resampled ×{factor:g} ({self.interpolation.value.value.lower()})",
            transform=transform,
        )


class Orientation(LabeledEnum):
    ROTATE_90_CLOCKWISE = "Rotate 90° clockwise"
    ROTATE_180 = "Rotate 180°"
    ROTATE_90_COUNTERCLOCKWISE = "Rotate 90° counterclockwise"
    FLIP_LEFT_RIGHT = "Flip left-right"
    FLIP_UP_DOWN = "Flip up-down"


def reorient(cube: np.ndarray, how: Orientation) -> tuple[np.ndarray, Affine]:
    """The rotated or flipped cube, and the affine from its pixel corners to
    the original's (so ``old_transform * affine`` georeferences it)."""
    rows, cols = cube.shape[:2]
    match how:
        case Orientation.ROTATE_90_CLOCKWISE:
            return np.rot90(cube, -1), Affine(0, 1, 0, -1, 0, rows)
        case Orientation.ROTATE_180:
            return np.rot90(cube, 2), Affine(-1, 0, cols, 0, -1, rows)
        case Orientation.ROTATE_90_COUNTERCLOCKWISE:
            return np.rot90(cube, 1), Affine(0, -1, cols, 1, 0, 0)
        case Orientation.FLIP_LEFT_RIGHT:
            return cube[:, ::-1], Affine(-1, 0, cols, 0, 1, 0)
        case Orientation.FLIP_UP_DOWN:
            return cube[::-1], Affine(1, 0, 0, 0, -1, rows)
    raise ValueError(f"Unknown orientation {how}")


class RotateFlipAnalysis(Analysis):
    analysisId = "rotate_flip"
    name = "Rotate / Flip"
    category = CATEGORY
    description = (
        "Rotate the image by quarter turns or mirror it. The georeferencing "
        "follows, so every pixel keeps its place on the map."
    )

    orientation = EnumParameter(
        "Operation", Orientation, Orientation.ROTATE_90_CLOCKWISE
    )

    def run(self, image: VardaRaster, reportProgress: ProgressCallback) -> VardaRaster:
        reportProgress(0, "reading image")
        cube, toOriginal = reorient(readCubeWithGaps(image), self.orientation.value)
        how = self.orientation.value.value
        return sameBandsRaster(
            image,
            np.ascontiguousarray(cube),
            name=f"{image.name} {how.lower()}",
            description=f"{image.name}, {how.lower()}",
            transform=image.transform * toOriginal,
        )


def _subsetMetadata(image: VardaRaster, bands: list[int]) -> dict:
    """The per-band metadata (FWHM, bad bands) for just ``bands``."""
    metadata = {}
    for key in BAND_METADATA_KEYS:
        value = image.extraMetadata.get(key)
        if value is None:
            continue
        try:
            values = parseEnviList(value)
        except (TypeError, ValueError):
            values = None
        if values is not None and len(values) == image.bandCount:
            metadata[key] = [values[b] for b in bands]
        else:
            metadata[key] = value  # one value for every band, e.g. the scale factor
    return metadata


class SubsetAnalysis(Analysis):
    analysisId = "subset"
    name = "Subset (Crop Rows, Columns, Bands)"
    category = CATEGORY
    description = (
        "Keep part of the image: a range of rows and columns (1-based, "
        "inclusive) and a list of bands like 1-100, 150-200. Wavelengths, "
        "band names, bad bands and the georeferencing follow."
    )

    firstRow = IntParameter("First Row", 1, range=(1, 1_000_000), description="1-based")
    lastRow = IntParameter(
        "Last Row", 1, range=(1, 1_000_000), description="1-based, inclusive"
    )
    firstColumn = IntParameter(
        "First Column", 1, range=(1, 1_000_000), description="1-based"
    )
    lastColumn = IntParameter(
        "Last Column", 1, range=(1, 1_000_000), description="1-based, inclusive"
    )
    bands = StringParameter("Bands", "", "e.g. 1-100, 150-200 (empty keeps all)")

    def prepareFor(self, image: VardaRaster) -> None:
        self.lastRow.set(image.height)
        self.lastColumn.set(image.width)

    def bandList(self, image: VardaRaster) -> list[int]:
        text = self.bands.value.strip()
        return (
            parsePositions(text, image.bandCount)
            if text
            else list(range(image.bandCount))
        )

    def unavailableReason(self, image: VardaRaster) -> str:
        if not (1 <= self.firstRow.value <= self.lastRow.value <= image.height):
            return f"Rows must run from 1 to {image.height}, first before last."
        if not (1 <= self.firstColumn.value <= self.lastColumn.value <= image.width):
            return f"Columns must run from 1 to {image.width}, first before last."
        if not self.bandList(image):
            return f"No bands between 1 and {image.bandCount} in {self.bands.value!r}."
        return ""

    def run(self, image: VardaRaster, reportProgress: ProgressCallback) -> VardaRaster:
        top, bottom = int(self.firstRow.value) - 1, int(self.lastRow.value)
        left, right = int(self.firstColumn.value) - 1, int(self.lastColumn.value)
        bands = self.bandList(image)
        reportProgress(0, "reading subset")
        data = image.getData(
            bandIndices=bands, window=(top, left, bottom - top, right - left)
        )
        cube = np.ma.filled(np.ma.asarray(data, dtype=np.float32), np.nan)
        default = [
            bands.index(b) for b in np.asarray(image.defaultBands).ravel() if b in bands
        ]
        source = ArrayDataSource(
            cube,
            wavelengths=np.asarray(image.wavelengths)[bands],
            wavelengthUnits=image.wavelengthUnits,
            bandNames=[image.bandNames[b] for b in bands],
            transform=image.transform * Affine.translation(left, top),
            crs=image.crs,
            nodata=image.nodata,
            defaultBands=np.array(default[:3]) if len(default) >= 3 else None,
            extraMetadata=_subsetMetadata(image, bands),
            description=f"Subset of {image.name}: rows {top + 1}-{bottom}, columns {left + 1}-{right}, {len(bands)} bands",
        )
        return VardaRaster(source, name=f"{image.name} subset")
