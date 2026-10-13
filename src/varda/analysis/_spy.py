"""Spectral Python (SPy), used only through this module.

Importing SPy adds a stderr handler to its logger and turns on console
progress bars; both are undone here, so SPy's messages go through Varda's
logging and nothing is printed. SPy's PySide6 viewers are never used.
Pinned to spectral>=0.24,<0.26 in pyproject.toml.
"""

from __future__ import annotations

import logging

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


def kmeans(
    X: np.ndarray, clusters: int, iterations: int
) -> tuple[np.ndarray, np.ndarray]:
    """(labels per pixel, cluster centres) for (pixels, bands) ``X``."""
    labels, centers = kmeans_ndarray(
        np.ascontiguousarray(X[:, None, :]),
        nclusters=clusters,
        max_iterations=iterations,
    )
    return np.asarray(labels).ravel(), np.asarray(centers)
