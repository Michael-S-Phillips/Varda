"""Geometric transforms between map coordinates, fitted from tie points.

The global transforms are 3×3 homogeneous matrices acting on (x, y) map
coordinates. Polynomials and thin-plate splines are ``Warp``s, for images
whose distortion varies across them (unprojected pushbroom strips, say).
Fits are done on centered, scaled coordinates (map coordinates can be in the
millions), then put back into map units."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
from scipy.interpolate import RBFInterpolator
from skimage import transform as sktransform

from varda.common.parameter import LabeledEnum


class TransformModel(LabeledEnum):
    TRANSLATION = "Translation"
    RIGID = "Rigid (shift and rotation)"
    SIMILARITY = "Similarity (and uniform scale)"
    AFFINE = "Affine"
    PROJECTIVE = "Projective"
    POLYNOMIAL2 = "Polynomial (2nd order)"
    POLYNOMIAL3 = "Polynomial (3rd order)"
    TPS = "Thin-plate spline (local warps)"


MIN_POINTS = {
    TransformModel.TRANSLATION: 1,
    TransformModel.RIGID: 2,
    TransformModel.SIMILARITY: 2,
    TransformModel.AFFINE: 3,
    TransformModel.PROJECTIVE: 4,
    TransformModel.POLYNOMIAL2: 6,
    TransformModel.POLYNOMIAL3: 10,
    TransformModel.TPS: 4,
}
WARPS = (TransformModel.POLYNOMIAL2, TransformModel.POLYNOMIAL3, TransformModel.TPS)
POLYNOMIAL_ORDER = {TransformModel.POLYNOMIAL2: 2, TransformModel.POLYNOMIAL3: 3}
# A little smoothing (in normalized units) keeps noisy automatic tie points
# from making the spline wiggle; exact points still fit to well under a pixel
TPS_SMOOTHING = 1e-7
MAX_TPS_POINTS = 1000
INVERSE_STEPS = 3
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
    if model in WARPS:
        raise ValueError(f"{model.value} is a warp: fit it with fitWarp.")
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


RANSAC_CONFIDENCE = 0.999
RANSAC_MAX_TRIALS = 2000

Mapping = Callable[[np.ndarray], np.ndarray]


def _ransac(
    fit: Callable[[np.ndarray, np.ndarray], Mapping],
    needed: int,
    src: np.ndarray,
    dst: np.ndarray,
    threshold: float,
    forced: np.ndarray,
) -> np.ndarray:
    """The inlier mask RANSAC settles on: minimal samples are fitted (``fit``
    returns the mapping), the one most points agree with wins, and the
    inliers are settled by refitting. Deterministic."""
    count = len(src)
    rng = np.random.default_rng(0)
    best = np.ones(count, bool)
    bestCount, bestError = -1, np.inf
    trials, trial = RANSAC_MAX_TRIALS, 0
    while trial < trials:
        trial += 1
        sample = rng.choice(count, needed, replace=False)
        try:
            mapping = fit(src[sample], dst[sample])
        except FitError:
            continue
        residuals = np.hypot(*(mapping(src) - dst).T)
        inliers = (residuals < threshold) | forced
        agreeing, error = int(inliers.sum()), float(residuals[inliers].sum())
        if agreeing > bestCount or (agreeing == bestCount and error < bestError):
            best, bestCount, bestError = inliers, agreeing, error
            # Enough trials to have drawn an all-inlier sample, with confidence
            share = agreeing / count
            if share >= 1.0:
                break
            trials = min(
                RANSAC_MAX_TRIALS,
                int(np.ceil(np.log(1 - RANSAC_CONFIDENCE) / np.log(1 - share**needed))),
            )
    for _ in range(2):  # settle the inliers on the refitted mapping
        mapping = fit(src[best], dst[best])
        residuals = np.hypot(*(mapping(src) - dst).T)
        inliers = (residuals < threshold) | forced
        if inliers.sum() < needed or np.array_equal(inliers, best):
            break
        best = inliers
    return best


def ransacFit(
    model: TransformModel,
    src: np.ndarray,
    dst: np.ndarray,
    threshold: float,
    forced: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """A matrix fit that ignores outliers (RANSAC, residual over
    ``threshold`` map units). ``forced`` points (manual ones) always count
    as inliers. Returns the matrix, every point's residual and the inlier
    mask."""
    src, dst = np.asarray(src, float), np.asarray(dst, float)
    forced = np.zeros(len(src), bool) if forced is None else np.asarray(forced, bool)
    needed = MIN_POINTS[model]
    if len(src) <= needed:
        matrix, residuals = fitTransform(model, src, dst)  # raises when too few

        return matrix, residuals, np.ones(len(src), bool)

    def fit(a: np.ndarray, b: np.ndarray) -> Mapping:
        matrix, _ = fitTransform(model, a, b)
        return lambda points: applyMatrix(matrix, points)

    inliers = _ransac(fit, needed, src, dst, threshold, forced)
    matrix, _ = fitTransform(model, src[inliers], dst[inliers])
    residuals = np.hypot(*(applyMatrix(matrix, src) - dst).T)
    return matrix, residuals, inliers


# --- warps -----------------------------------------------------------------------


def _monomials(points: np.ndarray, order: int) -> np.ndarray:
    """1, x, y, x², xy, y², … up to ``order``, for (N, 2) points."""
    x, y = points[:, 0], points[:, 1]
    return np.column_stack(
        [x ** (n - k) * y**k for n in range(order + 1) for k in range(n + 1)]
    )


class Warp:
    """A polynomial or thin-plate-spline mapping of map coordinates, fitted
    both ways (raw → corrected and back) to the same tie points. It's
    defined by its model and points, so it saves as them."""

    def __init__(self, model: TransformModel, src: np.ndarray, dst: np.ndarray):
        self.model = model
        self.src = np.asarray(src, float)
        self.dst = np.asarray(dst, float)
        both = np.concatenate([self.src, self.dst])
        self.center = both.mean(axis=0)
        self.scale = float(np.abs(both - self.center).max()) or 1.0
        a, b = self._normalize(self.src), self._normalize(self.dst)
        self._forward = self._fit(a, b)
        self._inverse = self._fit(b, a)

    def _normalize(self, points: np.ndarray) -> np.ndarray:
        return (np.asarray(points, float) - self.center) / self.scale

    def _fit(self, a: np.ndarray, b: np.ndarray) -> Mapping:
        if self.model is TransformModel.TPS:
            spline = RBFInterpolator(
                a, b - a, kernel="thin_plate_spline", smoothing=TPS_SMOOTHING
            )
            return lambda points: points + spline(points)
        order = POLYNOMIAL_ORDER[self.model]
        terms = _monomials(a, order)
        coefficients, _, rank, _ = np.linalg.lstsq(terms, b, rcond=None)
        if rank < terms.shape[1]:
            raise FitError(
                f"The tie points don't determine a {self.model.value.lower()} "
                "(spread them over the image)."
            )
        return lambda points: _monomials(points, order) @ coefficients

    def forward(self, points: np.ndarray) -> np.ndarray:
        """Raw map coordinates (N, 2) to corrected ones."""
        mapped = self._forward(self._normalize(np.atleast_2d(points)))
        return mapped * self.scale + self.center

    def inverse(self, points: np.ndarray) -> np.ndarray:
        """Corrected map coordinates (N, 2) back to raw ones: the fitted
        inverse, polished so that ``forward`` returns the points (the inverse
        of a polynomial isn't one; the warps are close to the identity, so
        fixed-point steps converge)."""
        target = self._normalize(np.atleast_2d(points))
        mapped = self._inverse(target)
        for _ in range(INVERSE_STEPS):
            mapped = mapped + (target - self._forward(mapped))
        return mapped * self.scale + self.center

    def state(self) -> dict:
        return {
            "model": self.model.name,
            "src": self.src.tolist(),
            "dst": self.dst.tolist(),
        }

    @classmethod
    def fromState(cls, state: dict) -> Warp:
        return cls(TransformModel[state["model"]], state["src"], state["dst"])


def fitWarp(
    model: TransformModel, src: np.ndarray, dst: np.ndarray
) -> tuple[Warp, np.ndarray]:
    """The warp taking ``src`` onto ``dst`` (both (N, 2), map units) and each
    point's residual."""
    src, dst = np.asarray(src, float), np.asarray(dst, float)
    needed = MIN_POINTS[model]
    if len(src) < needed:
        raise FitError(
            f"{model.value} needs at least {needed} tie points; there "
            f"{'is' if len(src) == 1 else 'are'} {len(src)}."
        )
    if np.linalg.matrix_rank(src - src.mean(axis=0), tol=1e-9 * (np.ptp(src) or 1)) < 2:
        raise FitError(
            f"The tie points don't determine a {model.value.lower()} (they're in a "
            "line); spread them out."
        )
    if model is TransformModel.TPS and len(src) > MAX_TPS_POINTS:
        keep = np.linspace(0, len(src) - 1, MAX_TPS_POINTS).astype(int)
        src, dst = src[keep], dst[keep]
    try:
        warp = Warp(model, src, dst)
    except np.linalg.LinAlgError as error:
        raise FitError(
            f"The {model.value.lower()} couldn't be fitted: {error}"
        ) from error
    return warp, np.hypot(*(warp.forward(src) - dst).T)


def robustWarpFit(
    model: TransformModel,
    src: np.ndarray,
    dst: np.ndarray,
    threshold: float,
    forced: np.ndarray | None = None,
) -> tuple[Warp, np.ndarray, np.ndarray]:
    """A warp fit that ignores outliers. Polynomials use RANSAC directly. A
    thin-plate spline reproduces any sample exactly, so its outliers are
    found by RANSAC with a looser cubic polynomial first; the spline is
    fitted to the rest. Returns the warp, every point's residual and the
    inlier mask."""
    src, dst = np.asarray(src, float), np.asarray(dst, float)
    forced = np.zeros(len(src), bool) if forced is None else np.asarray(forced, bool)

    def fit(kind: TransformModel) -> Callable[[np.ndarray, np.ndarray], Mapping]:
        return lambda a, b: fitWarp(kind, a, b)[0].forward

    if model is TransformModel.TPS:
        screen = next(
            (
                m
                for m in (TransformModel.POLYNOMIAL3, TransformModel.POLYNOMIAL2)
                if len(src) > MIN_POINTS[m]
            ),
            None,
        )
        inliers = (
            _ransac(fit(screen), MIN_POINTS[screen], src, dst, 3 * threshold, forced)
            if screen is not None
            else np.ones(len(src), bool)
        )
    elif len(src) > MIN_POINTS[model]:
        inliers = _ransac(fit(model), MIN_POINTS[model], src, dst, threshold, forced)
    else:
        inliers = np.ones(len(src), bool)
    warp, _ = fitWarp(model, src[inliers], dst[inliers])
    residuals = np.hypot(*(warp.forward(src) - dst).T)
    if model is TransformModel.TPS:  # points the spline follows after all count
        settled = (residuals < threshold) | forced
        if settled.sum() >= MIN_POINTS[model] and not np.array_equal(settled, inliers):
            inliers = settled
            warp, _ = fitWarp(model, src[inliers], dst[inliers])
            residuals = np.hypot(*(warp.forward(src) - dst).T)
    return warp, residuals, inliers
