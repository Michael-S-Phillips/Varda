"""Band depth: 1 - R(center) / R_continuum(center), with the continuum a
straight line between the reflectance at two shoulder wavelengths.

An example Varda plugin: one Analysis, registered with a hook, using only
``varda.api``. Its settings dialog is generated from the Parameters below.
"""

import numpy as np

from varda.api import Analysis, FloatParameter, hookimpl, readCube, singleBandRaster


def nearestBand(centers: np.ndarray, nm: float) -> int:
    return int(np.nanargmin(np.abs(centers - nm)))


def bandDepth(
    cube: np.ndarray, centers: np.ndarray, left: float, center: float, right: float
) -> np.ndarray:
    """Band depth per pixel; ``centers`` are the band centers in nm."""
    i, j, k = (nearestBand(centers, nm) for nm in (left, center, right))
    wl, wc, wr = centers[i], centers[j], centers[k]
    weight = (wc - wl) / (wr - wl)
    continuum = (1 - weight) * cube[:, :, i] + weight * cube[:, :, k]
    with np.errstate(divide="ignore", invalid="ignore"):
        return 1.0 - cube[:, :, j] / continuum


class BandDepth(Analysis):
    analysisId = "band_depth"
    name = "Band Depth"
    description = (
        "Depth of an absorption at a chosen wavelength, relative to a straight "
        "continuum between two shoulders (e.g. 1.9 µm water: 1.80, 1.93, 2.07 µm)."
    )
    category = "Spectral Parameters"

    left = FloatParameter("Left shoulder", 1800.0, (300.0, 5000.0), "nm")
    center = FloatParameter("Band center", 1930.0, (300.0, 5000.0), "nm")
    right = FloatParameter("Right shoulder", 2070.0, (300.0, 5000.0), "nm")

    def unavailableReason(self, image):
        if image.bandModel.centers is None:
            return f"{image.name} has no wavelengths in known units."
        return ""

    def run(self, image, reportProgress):
        left, center, right = (
            float(p.value) for p in (self.left, self.center, self.right)
        )
        if not left < center < right:
            raise ValueError("The band center must lie between the two shoulders.")
        reportProgress(0, "reading image")
        cube, valid = readCube(image)
        reportProgress(60, "computing band depth")
        depth = bandDepth(
            cube, np.asarray(image.bandModel.centers, float), left, center, right
        )
        depth[~valid] = np.nan
        label = f"BD{center:.0f}"
        return singleBandRaster(
            image, depth, name=f"{image.name} {label}", bandName=label
        )


@hookimpl
def registerAnalyses():
    return [BandDepth]
