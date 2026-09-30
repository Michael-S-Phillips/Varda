"""Transforms: PCA, MNF and ICA component images, and the inverse.

Choosing how many components matter is hard up front, so the forward
transforms default to every component and attach what an inverse needs to
the result. Flip through the component bands in a workspace to see where the
spatial coherence stops, then use Inverse Transform with that count to
rebuild a denoised image (or to keep just those components).
"""

from __future__ import annotations

from enum import Enum
from typing import ClassVar

import numpy as np
from PyQt6.QtWidgets import QWidget

from varda.analysis.analysis import Analysis, ProgressCallback
from varda.analysis.eigenvalue_plot import EigenvaluePlot
from varda.analysis.linear_algebra import (
    TransformResult,
    describeComponentSelection,
    fastIca,
    flattenValid,
    inverseTransform,
    mnf,
    noiseCovariance,
    pca,
    suggestedComponents,
    unflatten,
)
from varda.analysis.rasters import readCube
from varda.common.entities import VardaRaster
from varda.common.parameter import EnumParameter, IntParameter, MultiChoiceParameter
from varda.image_loading.data_sources.array_data_source import ArrayDataSource

TRANSFORM_METADATA_KEY = "transform"


def _componentsParameter() -> IntParameter:
    # Each analysis declares its own copy: ParameterGroup only picks up
    # Parameters defined directly on the class.
    return IntParameter(
        "Components",
        10,
        range=(1, 1000),
        description=(
            "How many components to compute; all of them by default, so the "
            "number to keep can be chosen afterwards with Inverse Transform."
        ),
    )


def transformMetadata(result: TransformResult, image: VardaRaster, kind: str) -> dict:
    """What Inverse Transform needs, as plain JSON-able types."""
    return {
        "kind": kind,
        "sourceName": image.name,
        "sourceWavelengths": [
            float(w) if image.wavelengthsType is not str else str(w)
            for w in image.wavelengths
        ],
        "sourceWavelengthUnits": image.wavelengthUnits,
        "sourceBandNames": list(image.bandNames),
        "mean": result.mean.tolist(),
        "inverse": result.inverse.tolist(),
        "eigenvalues": result.eigenvalues.tolist(),
        "explainedVariance": result.explainedVariance.tolist(),
    }


class _ComponentAnalysis(Analysis):
    """Shared plumbing: flatten valid pixels, transform, rebuild a raster."""

    category = "Transforms"
    suffix: ClassVar[str] = ""
    units: ClassVar[str] = "components"
    # Declared (not assigned) here: each subclass supplies its own Parameter.
    components: IntParameter

    def prepareFor(self, image: VardaRaster) -> None:
        self.components.setRange((1, image.bandCount), value=image.bandCount)

    def run(self, image: VardaRaster, reportProgress: ProgressCallback) -> VardaRaster:
        reportProgress(0, "reading image")
        cube, _ = readCube(image)  # bad bands filled, unusable pixels NaN
        X, valid = flattenValid(cube, None)
        components = min(int(self.components.value), image.bandCount)

        reportProgress(20, "computing components")
        result = self._transform(cube, X, valid, components)

        reportProgress(90, "building image")
        names = self._bandNames(result)
        data = unflatten(result.scores, valid).astype(np.float32)
        source = ArrayDataSource(
            data,
            wavelengths=np.array(names),
            wavelengthUnits=self.units,
            bandNames=names,
            transform=image.transform,
            crs=image.crs,
            description=f"{self.name} of {image.name}",
            extraMetadata={
                "explainedVariance": result.explainedVariance.tolist(),
                TRANSFORM_METADATA_KEY: transformMetadata(result, image, self.suffix),
            },
        )
        return VardaRaster(source, name=f"{image.name} {self.suffix}")

    def _transform(
        self, cube: np.ndarray, X: np.ndarray, valid: np.ndarray, components: int
    ) -> TransformResult:
        raise NotImplementedError

    def _bandNames(self, result: TransformResult) -> list[str]:
        raise NotImplementedError


class PcaAnalysis(_ComponentAnalysis):
    analysisId = "pca"
    name = "Principal Component Analysis (PCA)"
    description = (
        "Rotates the bands onto uncorrelated axes ordered by variance. Band "
        "names carry each component's share of the total variance."
    )
    suffix = "PCA"
    components = _componentsParameter()

    def _transform(self, cube, X, valid, components):
        return pca(X, components)

    def _bandNames(self, result):
        return [
            f"PC {i + 1} ({100 * share:.1f}%)"
            for i, share in enumerate(result.explainedVariance)
        ]


class MnfAnalysis(_ComponentAnalysis):
    analysisId = "mnf"
    name = "Minimum Noise Fraction (MNF)"
    description = (
        "Like PCA but ordered by signal-to-noise: the noise covariance is "
        "estimated from differences between neighbouring pixels and whitened "
        "away first, so the leading components hold coherent scene structure."
    )
    suffix = "MNF"
    components = _componentsParameter()

    def _transform(self, cube, X, valid, components):
        return mnf(X, noiseCovariance(cube, valid), components)

    def _bandNames(self, result):
        return [f"MNF {i + 1}" for i in range(result.scores.shape[1])]


class IcaAnalysis(_ComponentAnalysis):
    analysisId = "ica"
    name = "Independent Component Analysis (ICA)"
    description = (
        "FastICA on the leading principal components: finds statistically "
        "independent, non-Gaussian source images, e.g. to separate mixed "
        "spectral end-members."
    )
    suffix = "ICA"
    components = _componentsParameter()
    maxIterations = IntParameter(
        "Max Iterations",
        200,
        range=(10, 5000),
        description="Iteration cap for the FastICA fixed-point updates.",
    )

    def _transform(self, cube, X, valid, components):
        return fastIca(X, components, maxIterations=int(self.maxIterations.value))

    def _bandNames(self, result):
        return [f"IC {i + 1}" for i in range(result.scores.shape[1])]


class InverseOutput(Enum):
    DENOISED_IMAGE = "Denoised image (inverse transform to the original bands)"
    FIRST_COMPONENTS = "Only the first N components"


class InverseTransformAnalysis(Analysis):
    analysisId = "inverse_transform"
    name = "Inverse Transform (Keep N Components)"
    category = "Transforms"
    description = (
        "Decide how many PCA / MNF / ICA components carry signal, then either "
        "rebuild the image in its original bands from just those (dropping the "
        "noise in the rest) or keep only those component bands. The plot "
        "shows the eigenvalues: drag the cutoff to where they flatten out, and "
        "check the component images themselves for where spatial coherence "
        "stops."
    )

    components = IntParameter(
        "Components to keep",
        10,
        range=(1, 1000),
        description="Keep the first N components (ticks them in the list below).",
    )
    keep = MultiChoiceParameter(
        "Components",
        description=(
            "Exactly which components to use — untick e.g. component 1 to drop "
            "albedo, or type a range such as 3-19."
        ),
    )
    output = EnumParameter("Output", InverseOutput)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.components.sigParameterChanged.connect(self._reselectFirst)

    def _reselectFirst(self, count) -> None:
        if self.keep.choices:
            self.keep.set(self.keep.choices[: int(count)])

    @staticmethod
    def _info(image: VardaRaster) -> dict | None:
        return image.extraMetadata.get(TRANSFORM_METADATA_KEY)

    def unavailableReason(self, image: VardaRaster) -> str:
        if self._info(image) is None:
            return (
                "Inverse Transform works on the result of a PCA, MNF or ICA "
                "transform; run one first (keeping all components)."
            )
        if self.keep.choices and not self.keep.get():
            return "Tick at least one component to keep."
        return ""

    def prepareFor(self, image: VardaRaster) -> None:
        info = self._info(image)
        if info is None:
            return
        eigenvalues = np.asarray(info["eigenvalues"])
        suggested = suggestedComponents(eigenvalues, info["kind"])
        # Offer every component; the count below ticks the first N of them
        self.keep.setChoices(list(image.bandNames), selected=[])
        self.components.setRange((1, eigenvalues.size), value=suggested)
        self._reselectFirst(self.components.get())

    def createPreviewWidget(self, image: VardaRaster) -> QWidget | None:
        info = self._info(image)
        if info is None:
            return None
        return EigenvaluePlot(
            info["eigenvalues"], self.components, logScale=info["kind"] != "MNF"
        )

    def _selectedIndices(self, image: VardaRaster, total: int) -> list[int]:
        """0-based components to use: the ticked ones once prepared for an
        image, else the first N."""
        if self.keep.choices:
            chosen = set(self.keep.get())
            return [i for i, name in enumerate(self.keep.choices) if name in chosen]
        return list(range(min(int(self.components.value), total)))

    def run(self, image: VardaRaster, reportProgress: ProgressCallback) -> VardaRaster:
        info = self._info(image)
        if info is None:
            raise ValueError(self.unavailableReason(image))
        kind, sourceName = info["kind"], info["sourceName"]
        indices = self._selectedIndices(image, len(info["eigenvalues"]))
        if not indices:
            raise ValueError("Tick at least one component to keep.")
        which = describeComponentSelection(indices)

        reportProgress(0, "reading components")
        cube, _ = readCube(image)
        if self.output.value is InverseOutput.FIRST_COMPONENTS:
            kept = {
                **info,
                "inverse": [info["inverse"][i] for i in indices],
                "eigenvalues": [info["eigenvalues"][i] for i in indices],
                "explainedVariance": [info["explainedVariance"][i] for i in indices],
            }
            source = ArrayDataSource(
                cube[:, :, indices].astype(np.float32),
                wavelengths=np.array([image.wavelengths[i] for i in indices]),
                wavelengthUnits=image.wavelengthUnits,
                bandNames=[image.bandNames[i] for i in indices],
                transform=image.transform,
                crs=image.crs,
                nodata=image.nodata,
                description=f"{which.capitalize()} of {image.name}",
                extraMetadata={**image.extraMetadata, TRANSFORM_METADATA_KEY: kept},
            )
            return VardaRaster(source, name=f"{sourceName} {kind} ({which})")

        scores, valid = flattenValid(cube, None)
        reportProgress(30, f"rebuilding from {which}")
        rebuilt = inverseTransform(
            scores, np.asarray(info["inverse"]), np.asarray(info["mean"]), indices
        )
        reportProgress(85, "building image")
        source = ArrayDataSource(
            unflatten(rebuilt, valid).astype(np.float32),
            wavelengths=np.array(info["sourceWavelengths"]),
            wavelengthUnits=info["sourceWavelengthUnits"],
            bandNames=list(info["sourceBandNames"]),
            transform=image.transform,
            crs=image.crs,
            description=f"{sourceName} rebuilt from {kind} {which}",
        )
        return VardaRaster(source, name=f"{sourceName} {kind} inverse ({which})")
