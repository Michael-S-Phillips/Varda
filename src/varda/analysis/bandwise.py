"""Spatial operations applied band by band: the shared base for filters,
texture measures and the like.

A ``BandwiseAnalysis`` runs on every band (a result with the image's bands)
or on one (a one-band result). No-data pixels are filled from their nearest
valid neighbor before the band is processed, so a filter never smears NaN
across the image, and put back as NaN afterwards.
"""

from __future__ import annotations


import numpy as np
from scipy import ndimage

from varda.analysis.analysis import Analysis, ProgressCallback
from varda.analysis.rasters import bandIndex, sameBandsRaster, singleBandRaster
from varda.common.entities import VardaRaster
from varda.common.parameter import LabeledEnum, EnumParameter, IntParameter


class BandScope(LabeledEnum):
    ALL_BANDS = "All bands"
    ONE_BAND = "One band"


def readBand(image: VardaRaster, index: int) -> np.ndarray:
    """Band ``index`` (0-based) as float64, NaN where it's no-data."""
    band = np.ma.filled(
        np.ma.asarray(image.getData(bandIndices=[index]), dtype=np.float64)[:, :, 0],
        np.nan,
    )
    if image.nodata is not None:
        band[band == image.nodata] = np.nan
    return band


def fillGaps(band: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """``band`` with each NaN replaced by its nearest valid value, and the
    mask of where the NaNs were. An all-NaN band comes back as zeros."""
    missing = ~np.isfinite(band)
    if not missing.any():
        return band, missing
    if missing.all():
        return np.zeros_like(band), missing
    nearest = ndimage.distance_transform_edt(
        missing, return_distances=False, return_indices=True
    )
    return band[tuple(nearest)], missing


def oddSize(size: int) -> int:
    """A window size made odd (centered windows), at least 1."""
    size = max(int(size), 1)
    return size if size % 2 else size + 1


class BandwiseAnalysis(Analysis):
    """Subclasses implement ``processBand`` (a gap-free 2-D float64 band in,
    the same shape out) and ``label`` (what the result is called)."""

    scope = EnumParameter(
        "Bands",
        BandScope,
        BandScope.ALL_BANDS,
        "Process every band (a result with all the bands) or just one.",
    )
    band = IntParameter(
        "Band",
        1,
        range=(1, 10000),
        description="The band to process (1-based) for One band",
    )

    def label(self) -> str:
        return self.name

    def processBand(self, band: np.ndarray) -> np.ndarray:
        raise NotImplementedError

    def bandIndices(self, image: VardaRaster) -> list[int]:
        if self.scope.value is BandScope.ONE_BAND:
            return [bandIndex(image, int(self.band.value))]
        return list(range(image.bandCount))

    def run(self, image: VardaRaster, reportProgress: ProgressCallback) -> VardaRaster:
        indices = self.bandIndices(image)
        output = np.empty((image.height, image.width, len(indices)), np.float32)
        for i, index in enumerate(indices):
            reportProgress(int(100 * i / len(indices)), f"band {index + 1}")
            filled, missing = fillGaps(readBand(image, index))
            result = np.asarray(self.processBand(filled), dtype=np.float64)
            result[missing] = np.nan
            output[:, :, i] = result
        label = self.label()
        if self.scope.value is BandScope.ONE_BAND:
            index = indices[0]
            return singleBandRaster(
                image,
                output[:, :, 0],
                name=f"{image.name} {label} (band {index + 1})",
                bandName=f"{label} of band {index + 1}",
                description=f"{label} of band {index + 1} of {image.name}",
            )
        return sameBandsRaster(
            image,
            output,
            name=f"{image.name} {label}",
            description=f"{label} of {image.name}",
        )
