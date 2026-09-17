"""Band Parameters: a chosen set of HyPyRameter spectral parameters."""

from __future__ import annotations

import numpy as np

from varda.analysis.analysis import Analysis, ProgressCallback
from varda.analysis.hypyrameter_adapter import (
    HYPYRAMETER_AVAILABLE,
    computeParameterCube,
    toNanometres,
    validParameterNames,
)
from varda.common.entities import VardaRaster
from varda.common.parameter import BoolParameter, MultiChoiceParameter
from varda.image_loading.data_sources.array_data_source import ArrayDataSource

# HyPyRameter's own default display bands for a parameter cube
_DEFAULT_DISPLAY = ("R637", "R550", "R463")


class BandParametersAnalysis(Analysis):
    analysisId = "band_parameters"
    name = "Band Parameters (HyPyRameter)"
    category = "Spectral Parameters"
    requirement = "HyPyRameter"
    description = (
        "Computes the chosen HyPyRameter spectral parameters and produces a "
        "parameter image with one band per parameter. The list offers every "
        "parameter the image's wavelength range supports."
    )

    parameters = MultiChoiceParameter(
        "Parameters",
        description="The spectral parameters to compute (all supported ones by default).",
    )
    clampReflectance = BoolParameter(
        "Clamp reflectance to [-1, 1]",
        True,
        "Treat values outside [-1, 1] as missing, as HyPyRameter does for "
        "reflectance cubes.",
    )

    @classmethod
    def isAvailable(cls) -> bool:
        return HYPYRAMETER_AVAILABLE

    def prepareFor(self, image: VardaRaster) -> None:
        self.parameters.setChoices(self._supportedNames(image))

    @staticmethod
    def _supportedNames(image: VardaRaster) -> list[str]:
        if image.wavelengthsType is str:
            return []
        return validParameterNames(toNanometres(image.wavelengths))

    def _chosenNames(self, image: VardaRaster) -> list[str]:
        supported = self._supportedNames(image)
        if not supported:
            raise ValueError(
                f"No HyPyRameter parameter fits the wavelength range of {image.name}."
            )
        if not self.parameters.choices:  # never prepared for an image: compute all
            return supported
        names = [name for name in self.parameters.get() if name in supported]
        if not names:
            raise ValueError("Select at least one parameter to compute.")
        return names

    def run(self, image: VardaRaster, reportProgress: ProgressCallback) -> VardaRaster:
        if image.wavelengthsType is str:
            raise ValueError(
                f"{image.name} has no numeric wavelengths; band parameters need "
                "wavelengths in nm or µm."
            )
        names = self._chosenNames(image)
        reportProgress(0, "reading image")
        cube = np.asarray(image.getData(), dtype=np.float64)
        if image.nodata is not None:
            cube[cube == image.nodata] = np.nan
        if self.clampReflectance.value:
            cube[np.abs(cube) > 1.0] = np.nan

        wavelengths = toNanometres(image.wavelengths)
        parameters = computeParameterCube(cube, wavelengths, names, reportProgress)

        display = [names.index(n) for n in _DEFAULT_DISPLAY if n in names]
        source = ArrayDataSource(
            parameters,
            wavelengths=np.array(names),
            wavelengthUnits="parameters",
            bandNames=names,
            transform=image.transform,
            crs=image.crs,
            isParameterImage=True,
            defaultBands=np.array(display) if len(display) == 3 else None,
            description=f"HyPyRameter spectral parameters of {image.name}",
        )
        return VardaRaster(source, name=f"{image.name} parameters")
