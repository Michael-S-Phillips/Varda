"""Transforms: PCA, MNF and ICA component images."""

from __future__ import annotations

from typing import ClassVar

import numpy as np

from varda.analysis.analysis import Analysis, ProgressCallback
from varda.analysis.linear_algebra import (
    TransformResult,
    fastIca,
    flattenValid,
    mnf,
    noiseCovariance,
    pca,
    unflatten,
)
from varda.common.entities import VardaRaster
from varda.common.parameter import IntParameter
from varda.image_loading.data_sources.array_data_source import ArrayDataSource


def _componentsParameter() -> IntParameter:
    # Each analysis declares its own copy: ParameterGroup only picks up
    # Parameters defined directly on the class.
    return IntParameter(
        "Components",
        10,
        range=(1, 1000),
        description="How many components to keep (at most the number of bands).",
    )


class _ComponentAnalysis(Analysis):
    """Shared plumbing: flatten valid pixels, transform, rebuild a raster."""

    category = "Transforms"
    suffix: ClassVar[str] = ""
    units: ClassVar[str] = "components"
    # Declared (not assigned) here: each subclass supplies its own Parameter.
    components: IntParameter

    def run(self, image: VardaRaster, reportProgress: ProgressCallback) -> VardaRaster:
        reportProgress(0, "reading image")
        cube = np.asarray(image.getData(), dtype=np.float64)
        X, valid = flattenValid(cube, image.nodata)
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
            extraMetadata={"explainedVariance": result.explainedVariance.tolist()},
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
        sources, mixing = fastIca(
            X, components, maxIterations=int(self.maxIterations.value)
        )
        share = np.full(sources.shape[1], 1.0 / sources.shape[1])
        return TransformResult(scores=sources, loadings=mixing, explainedVariance=share)

    def _bandNames(self, result):
        return [f"IC {i + 1}" for i in range(result.scores.shape[1])]
