"""Statistical classifiers: Gaussian maximum likelihood and Mahalanobis
distance (trained on ROI classes, through SPy), and k-means clustering.

SPy silently leaves out any class with fewer training pixels than bands --
on a 400-band CRISM cube, that is most ROIs. Here the data are first reduced
to principal components when a class is too small for the full band count
(or to a number you choose), and a class too small even for that is reported
by name instead of vanishing.
"""

from __future__ import annotations

import numpy as np
from spectral.algorithms.algorithms import create_training_classes

from varda.analysis import _spy
from varda.analysis.analysis import Analysis, ProgressCallback
from varda.analysis.classification import (
    _classificationRaster,
    _requireRois,
    _roiChoiceParameter,
    _RoiTrainingAnalysis,
)
from varda.analysis.linear_algebra import pca
from varda.analysis.rasters import readCube
from varda.common.entities import VardaRaster
from varda.common.palette import classColor
from varda.common.parameter import IntParameter
from varda.image_loading.data_sources.array_data_source import ArrayDataSource

MIN_CLASS_PIXELS = 3
MAX_AUTO_COMPONENTS = 30


def _componentsParameter() -> IntParameter:
    return IntParameter(
        "Components",
        0,
        range=(0, 200),
        description=(
            "Principal components to classify on; 0 = all bands, reduced "
            "automatically when a class has too few pixels for them."
        ),
    )


def chooseComponents(bands: int, smallestClass: int, requested: int) -> int:
    """How many dimensions to classify in: each class needs more pixels than
    dimensions for its covariance to be invertible."""
    if requested > 0:
        return min(requested, bands, smallestClass - 1)
    if smallestClass >= 2 * bands:
        return bands
    return int(np.clip(smallestClass // 2, 2, min(MAX_AUTO_COMPONENTS, bands)))


def _softmax(scores: np.ndarray) -> np.ndarray:
    shifted = scores - scores.max(axis=1, keepdims=True)
    weights = np.exp(shifted)
    return weights / weights.sum(axis=1, keepdims=True)


class _GaussianClassification(_RoiTrainingAnalysis):
    suffix = ""
    components: IntParameter  # declared here, assigned by each subclass

    def _classifier(self, training, minSamples: int):
        raise NotImplementedError

    def _scores(self, classifier, Y: np.ndarray) -> np.ndarray:
        """(pixels, classes) log-likelihood-like scores."""
        raise NotImplementedError

    def run(self, image: VardaRaster, reportProgress: ProgressCallback) -> VardaRaster:
        rois = _requireRois(self)
        names = self._chosenClasses(rois)
        if len(names) < 2:
            raise ValueError("Training needs at least two ROI classes.")
        reportProgress(0, "reading image")
        cube, valid = readCube(image)
        labels = np.zeros(valid.shape, dtype=np.int64)  # 0 = not training
        for k, name in enumerate(names, start=1):
            labels[rois.classMask(name, image) & valid] = k
        sizes = {
            name: int((labels == k).sum()) for k, name in enumerate(names, start=1)
        }
        tooSmall = [n for n, size in sizes.items() if size < MIN_CLASS_PIXELS]
        if tooSmall:
            raise ValueError(
                f"ROI class {', '.join(tooSmall)} has fewer than {MIN_CLASS_PIXELS} "
                "valid pixels; draw a larger ROI."
            )
        bands = cube.shape[2]
        k = chooseComponents(bands, min(sizes.values()), int(self.components.value))

        reportProgress(20, f"training on {k} dimensions")
        X = cube[valid]
        if k < bands:
            X = pca(X, k).scores
        reduced = np.zeros(valid.shape + (k,))
        reduced[valid] = X
        training = create_training_classes(reduced, labels, calc_stats=True)
        classifier = self._classifier(training, k + 1)
        if len(classifier.classes) != len(names):
            raise ValueError("A training class was too small to use; draw larger ROIs.")

        reportProgress(60, "classifying")
        order = np.argsort([cl.index for cl in classifier.classes])  # class 1..n
        probabilities = _softmax(self._scores(classifier, X)[:, order])
        return _classificationRaster(
            image,
            valid,
            probabilities,
            names,
            colors=self._classColors(rois, names),
            suffix=self.suffix,
            metadata={"components": k},
        )


class MaximumLikelihoodAnalysis(_GaussianClassification):
    analysisId = "maximum_likelihood"
    software = ("spectral",)
    name = "Maximum Likelihood"
    suffix = "ML classes"
    description = (
        "Gaussian maximum-likelihood classification: each ROI class is "
        "modeled by its mean and covariance, and every pixel goes to the "
        "most likely class."
    )
    rois = _roiChoiceParameter()
    components = _componentsParameter()

    def _classifier(self, training, minSamples):
        return _spy.GaussianClassifier(training, min_samples=minSamples)

    def _scores(self, classifier, Y):
        columns = []
        for cl in classifier.classes:
            delta = Y - cl.stats.mean
            mahalanobis = np.einsum("ij,jk,ik->i", delta, cl.stats.inv_cov, delta)
            columns.append(-0.5 * cl.stats.log_det_cov - 0.5 * mahalanobis)
        return np.column_stack(columns)


class MahalanobisAnalysis(_GaussianClassification):
    analysisId = "mahalanobis"
    software = ("spectral",)
    name = "Mahalanobis Distance"
    suffix = "Mahalanobis classes"
    description = (
        "Mahalanobis-distance classification: every pixel goes to the class "
        "whose mean is nearest, measured with the classes' pooled covariance."
    )
    rois = _roiChoiceParameter()
    components = _componentsParameter()

    def _classifier(self, training, minSamples):
        return _spy.MahalanobisDistanceClassifier(training, min_samples=minSamples)

    def _scores(self, classifier, Y):
        inverse = classifier.background.inv_cov
        columns = []
        for cl in classifier.classes:
            delta = Y - cl.stats.mean
            columns.append(-0.5 * np.einsum("ij,jk,ik->i", delta, inverse, delta))
        return np.column_stack(columns)


class KMeansAnalysis(Analysis):
    analysisId = "kmeans"
    software = ("spectral",)
    name = "K-Means Clustering"
    category = "Classification"
    description = (
        "Unsupervised: groups the pixels into clusters of similar spectra, "
        "with no ROIs needed. A starting point for finding materials."
    )

    clusters = IntParameter(
        "Clusters", 8, range=(2, 50), description="Clusters to find"
    )
    iterations = IntParameter(
        "Iterations", 20, range=(1, 200), description="Maximum iterations"
    )

    def run(self, image: VardaRaster, reportProgress: ProgressCallback) -> VardaRaster:
        reportProgress(0, "reading image")
        cube, valid = readCube(image)
        reportProgress(20, "clustering")
        labels, _centres = _spy.kmeans(
            cube[valid], int(self.clusters.value), int(self.iterations.value)
        )
        found = np.unique(labels)
        renumbered = np.searchsorted(found, labels)  # 0..n-1 for the clusters found
        classes = np.full(valid.shape, np.nan, dtype=np.float32)
        classes[valid] = renumbered
        names = [f"Cluster {i + 1}" for i in range(found.size)]
        source = ArrayDataSource(
            classes[:, :, None],
            wavelengths=np.array(["Class"]),
            wavelengthUnits="classes",
            bandNames=["Class"],
            transform=image.transform,
            crs=image.crs,
            description=f"K-means ({found.size} clusters) of {image.name}",
            extraMetadata={
                "classes": names,
                "classColors": [classColor(i) for i in range(found.size)],
            },
        )
        return VardaRaster(source, name=f"{image.name} k-means")
