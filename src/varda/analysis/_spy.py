"""Spectral Python (SPy), used only through this module.

Importing SPy adds a stderr handler to its logger and turns on console
progress bars; both are undone here, so SPy's messages go through Varda's
logging and nothing is printed. SPy's PySide6 viewers are never used.
Pinned to spectral>=0.24,<0.26 in pyproject.toml.
"""

from __future__ import annotations

import logging

import attrs
import numpy as np
import spectral
from spectral.algorithms.algorithms import GaussianStats, calc_stats
from spectral.algorithms.classifiers import (
    GaussianClassifier,
    MahalanobisDistanceClassifier,
)
from spectral.algorithms.clustering import kmeans_ndarray
from spectral.algorithms.detectors import ACE, RX, MatchedFilter
from spectral.algorithms.resampling import create_resampling_matrix

_spyLogger = logging.getLogger("spectral")
for _handler in list(_spyLogger.handlers):
    _spyLogger.removeHandler(_handler)
spectral.settings.show_progress = False

__all__ = [
    "ACE",
    "RX",
    "GaussianClassifier",
    "GaussianStats",
    "KMeansResult",
    "MahalanobisDistanceClassifier",
    "MatchedFilter",
    "backgroundStats",
    "kmeans",
    "resamplingMatrix",
    "spectral",
]


def resamplingMatrix(
    centers1: np.ndarray, fwhm1: np.ndarray, centers2: np.ndarray, fwhm2: np.ndarray
) -> np.ndarray:
    """(bands2, bands1) matrix taking spectra sampled at (centers1, fwhm1) to
    Gaussian bands (centers2, fwhm2). All in the same unit."""
    return np.asarray(
        create_resampling_matrix(
            list(centers1), list(fwhm1), list(centers2), list(fwhm2)
        ),
        dtype=np.float64,
    )


def backgroundStats(
    X: np.ndarray, maxSamples: int = 200_000, seed: int = 0
) -> GaussianStats:
    """Mean and covariance of (pixels, bands) ``X`` (a random subset of at most
    ``maxSamples`` pixels for very large images)."""
    if X.shape[0] > maxSamples:
        rows = np.random.default_rng(seed).choice(X.shape[0], maxSamples, replace=False)
        X = X[rows]
    return calc_stats(np.ascontiguousarray(X[:, None, :]))


@attrs.frozen
class KMeansResult:
    labels: np.ndarray  # cluster per pixel (SPy's numbering)
    centers: np.ndarray  # (clusters, bands) SPy's last centers
    iterations: int  # iterations run
    converged: bool  # True when the last iteration reassigned no pixel
    changed: int  # pixels reassigned in the last iteration


def kmeans(X: np.ndarray, clusters: int, iterations: int) -> KMeansResult:
    """k-means of (pixels, bands) ``X`` by SPy, with how it ended."""
    changes: list[int] = []

    def compare(old: np.ndarray, new: np.ndarray) -> bool:
        # SPy calls this once per iteration; True stops it, as SPy itself
        # stops when no pixel is reassigned
        changes.append(int(np.count_nonzero(old != new)))
        return changes[-1] == 0

    labels, centers = kmeans_ndarray(
        np.ascontiguousarray(X[:, None, :]),
        nclusters=clusters,
        max_iterations=iterations,
        compare=compare,
    )
    return KMeansResult(
        labels=np.asarray(labels).ravel(),
        centers=np.asarray(centers),
        iterations=len(changes),
        converged=bool(changes) and changes[-1] == 0,
        changed=changes[-1] if changes else 0,
    )
