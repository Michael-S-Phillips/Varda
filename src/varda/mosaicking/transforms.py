"""Geometric transforms between map coordinates, fitted from tie points.

A transform is a 3×3 homogeneous matrix acting on (x, y) map coordinates.
Fits are done on centered, scaled coordinates (map coordinates can be in the
millions), then put back into map units."""

from __future__ import annotations

import numpy as np
from skimage import transform as sktransform

from varda.common.parameter import LabeledEnum


class TransformModel(LabeledEnum):
    TRANSLATION = "Translation"
    RIGID = "Rigid (shift and rotation)"
    SIMILARITY = "Similarity (and uniform scale)"
    AFFINE = "Affine"
    PROJECTIVE = "Projective"


MIN_POINTS = {
    TransformModel.TRANSLATION: 1,
    TransformModel.RIGID: 2,
    TransformModel.SIMILARITY: 2,
    TransformModel.AFFINE: 3,
    TransformModel.PROJECTIVE: 4,
}
_SKIMAGE = {
    TransformModel.RIGID: sktransform.EuclideanTransform,
    TransformModel.SIMILARITY: sktransform.SimilarityTransform,
    TransformModel.AFFINE: sktransform.AffineTransform,
    TransformModel.PROJECTIVE: sktransform.ProjectiveTransform,
}


class FitError(ValueError):
    """A transform couldn't be fitted; the message says why, for the user."""


def translation(dx: float, dy: float) -> np.ndarray:
    return np.array([[1.0, 0.0, dx], [0.0, 1.0, dy], [0.0, 0.0, 1.0]])


def applyMatrix(matrix: np.ndarray, points: np.ndarray) -> np.ndarray:
    """(N, 2) points through a 3×3 homogeneous matrix."""
    points = np.atleast_2d(np.asarray(points, dtype=float))
    homogeneous = np.column_stack([points, np.ones(len(points))]) @ matrix.T
    return homogeneous[:, :2] / homogeneous[:, 2:3]


def _estimate(cls, src: np.ndarray, dst: np.ndarray) -> np.ndarray | None:
    """scikit-image's fit for ``cls``: ``from_estimate`` (0.26+) or ``estimate``."""
    if hasattr(cls, "from_estimate"):
        result = cls.from_estimate(src, dst)
        return result.params if result else None
    tform = cls()
    return tform.params if tform.estimate(src, dst) else None


def fitTransform(
    model: TransformModel, src: np.ndarray, dst: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """The matrix taking ``src`` points onto ``dst`` (both (N, 2), map units)
    and each point's residual distance after the fit."""
    src, dst = np.asarray(src, float), np.asarray(dst, float)
    needed = MIN_POINTS[model]
    if len(src) < needed:
        raise FitError(
            f"{model.value} needs at least {needed} tie point{'s' if needed > 1 else ''}; "
            f"there {'is' if len(src) == 1 else 'are'} {len(src)}."
        )
    if model is TransformModel.TRANSLATION:
        dx, dy = (dst - src).mean(axis=0)
        matrix = translation(dx, dy)
    elif (
        needed > 2
        and np.linalg.matrix_rank(src - src.mean(axis=0), tol=1e-9 * (np.ptp(src) or 1))
        < 2
    ):
        raise FitError(
            f"The tie points don't determine a {model.value.lower()} transform "
            "(they're in a line); spread them out."
        )
    else:
        center = src.mean(axis=0)
        scale = float(np.abs(np.concatenate([src, dst]) - center).max()) or 1.0
        normalize = np.array(
            [
                [1 / scale, 0, -center[0] / scale],
                [0, 1 / scale, -center[1] / scale],
                [0, 0, 1],
            ]
        )
        params = _estimate(
            _SKIMAGE[model], applyMatrix(normalize, src), applyMatrix(normalize, dst)
        )
        if params is None:
            raise FitError(
                f"The tie points don't determine a {model.value.lower()} transform (are they in a line?)."
            )
        matrix = np.linalg.inv(normalize) @ params @ normalize
    residuals = np.hypot(*(applyMatrix(matrix, src) - dst).T)
    return matrix, residuals
