"""Derivatives: spectral derivative, spectral slope, spatial gradient."""

from __future__ import annotations

import numpy as np
from scipy import ndimage

from varda.analysis.analysis import Analysis, ProgressCallback
from varda.analysis.rasters import bandIndex, singleBandRaster, validPixels
from varda.common.entities import VardaRaster
from varda.common.parameter import FloatParameter, IntParameter
from varda.image_loading.data_sources.array_data_source import ArrayDataSource


def _numericWavelengths(image: VardaRaster) -> np.ndarray | None:
    if image.wavelengthsType is str:
        return None
    return np.asarray(image.wavelengths, dtype=np.float64)


class SpectralDerivativeAnalysis(Analysis):
    analysisId = "spectral_derivative"
    name = "Spectral Derivative"
    category = "Derivatives"
    description = (
        "Derivative of each spectrum with respect to wavelength, band by band "
        "(or the second derivative): highlights absorption edges and band "
        "centres. Without numeric wavelengths, band index is the x axis."
    )

    order = IntParameter("Order", 1, range=(1, 2), description="1 = dR/dλ, 2 = d²R/dλ²")

    def run(self, image: VardaRaster, reportProgress: ProgressCallback) -> VardaRaster:
        reportProgress(0, "reading image")
        cube = np.asarray(image.getData(), dtype=np.float64)
        cube[~validPixels(cube, image.nodata)] = np.nan
        wavelengths = _numericWavelengths(image)
        x = (
            wavelengths
            if wavelengths is not None
            else np.arange(image.bandCount, dtype=float)
        )

        reportProgress(40, "differentiating")
        derivative = cube
        for _ in range(int(self.order.value)):
            derivative = np.gradient(derivative, x, axis=2)

        suffix = "d/dλ" if int(self.order.value) == 1 else "d²/dλ²"
        source = ArrayDataSource(
            derivative.astype(np.float32),
            wavelengths=np.asarray(image.wavelengths),
            wavelengthUnits="per nm" if wavelengths is not None else "per band",
            bandNames=list(image.bandNames),
            transform=image.transform,
            crs=image.crs,
            description=f"{suffix} of {image.name}",
        )
        return VardaRaster(source, name=f"{image.name} {suffix}")


class SpectralSlopeAnalysis(Analysis):
    analysisId = "spectral_slope"
    name = "Spectral Slope"
    category = "Derivatives"
    description = (
        "Least-squares slope of each spectrum between two wavelengths "
        "(reflectance per nm), e.g. the 1.8-2.5 µm slope used to flag "
        "hydrated phases."
    )

    startWavelength = FloatParameter(
        "Start Wavelength", 1000.0, units="nm", description="Start of the fitted range"
    )
    endWavelength = FloatParameter(
        "End Wavelength", 2000.0, units="nm", description="End of the fitted range"
    )

    def run(self, image: VardaRaster, reportProgress: ProgressCallback) -> VardaRaster:
        wavelengths = _numericWavelengths(image)
        if wavelengths is None:
            raise ValueError(
                f"{image.name} has no numeric wavelengths to fit a slope over."
            )
        low = min(float(self.startWavelength.value), float(self.endWavelength.value))
        high = max(float(self.startWavelength.value), float(self.endWavelength.value))
        selected = np.where((wavelengths >= low) & (wavelengths <= high))[0]
        if selected.size < 2:
            raise ValueError(
                f"Fewer than two bands fall in the wavelength range {low:g}-{high:g}."
            )

        reportProgress(0, "reading bands")
        cube = np.asarray(image.getData(bandIndices=list(selected)), dtype=np.float64)
        valid = validPixels(cube, image.nodata)

        reportProgress(50, "fitting slopes")
        xCentred = wavelengths[selected] - wavelengths[selected].mean()
        yCentred = cube - cube.mean(axis=2, keepdims=True)
        slope = np.tensordot(yCentred, xCentred, axes=([2], [0])) / np.sum(xCentred**2)
        slope[~valid] = np.nan

        return singleBandRaster(
            image,
            slope,
            name=f"{image.name} slope {low:g}-{high:g}",
            bandName=f"Slope {low:g}-{high:g} nm",
            units="per nm",
        )


class SpatialGradientAnalysis(Analysis):
    analysisId = "spatial_gradient"
    name = "Spatial Gradient"
    category = "Derivatives"
    description = (
        "Magnitude of the spatial gradient (Sobel) of one band, in band units "
        "per pixel: bright where the band changes quickly, e.g. at unit "
        "boundaries."
    )

    band = IntParameter("Band", 1, range=(1, 10000), description="Band (1-based)")

    def run(self, image: VardaRaster, reportProgress: ProgressCallback) -> VardaRaster:
        reportProgress(0, "reading band")
        index = bandIndex(image, int(self.band.value))
        data = np.asarray(image.getData(bandIndices=[index]), dtype=np.float64)[:, :, 0]
        if image.nodata is not None:
            data[data == image.nodata] = np.nan

        reportProgress(50, "computing gradient")
        # Sobel kernels sum to 8 across a unit ramp, so /8 gives the per-pixel slope
        gx = ndimage.sobel(data, axis=1, mode="nearest") / 8.0
        gy = ndimage.sobel(data, axis=0, mode="nearest") / 8.0
        magnitude = np.hypot(gx, gy)

        return singleBandRaster(
            image,
            magnitude,
            name=f"{image.name} gradient (band {index + 1})",
            bandName="Gradient magnitude",
            units="per pixel",
        )
