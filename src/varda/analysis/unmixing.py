"""Mapping endmembers across an image: spectral angles, linear unmixing and
mixture-tuned matched filtering (MTMF). Pure numpy.

Data are (pixels, bands) matrices; endmembers are (endmembers, bands). Rows
with a non-finite value give NaN results.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum

import numpy as np

_CHUNK = 16_384
_ADMM_ITERATIONS = 2000
# Up to this many endmembers the fully constrained solution is found exactly
# by trying every support set (2^m - 1 small solves, vectorized over pixels)
_EXACT_MAX_ENDMEMBERS = 10


class Constraint(Enum):
    NONE = "Unconstrained"
    SUM_TO_ONE = "Sum to one"
    FULLY_CONSTRAINED = "Sum to one, non-negative (FCLS)"


def _finiteRows(X: np.ndarray) -> np.ndarray:
    return np.all(np.isfinite(X), axis=1)


def spectralAngles(X: np.ndarray, endmembers: np.ndarray) -> np.ndarray:
    """Angle (radians) between every row of ``X`` and every endmember:
    (pixels, endmembers). Insensitive to brightness (vector length)."""
    data = np.asarray(X, dtype=np.float64)
    E = np.asarray(endmembers, dtype=np.float64)
    En = E / np.linalg.norm(E, axis=1, keepdims=True)
    out = np.full((data.shape[0], E.shape[0]), np.nan)
    good = np.flatnonzero(_finiteRows(data))
    for start in range(0, good.size, _CHUNK):
        rows = good[start : start + _CHUNK]
        block = data[rows]
        norms = np.linalg.norm(block, axis=1, keepdims=True)
        with np.errstate(invalid="ignore", divide="ignore"):
            cosines = (block / norms) @ En.T
        out[rows] = np.arccos(np.clip(cosines, -1.0, 1.0))
    return out


def linearUnmix(
    X: np.ndarray,
    endmembers: np.ndarray,
    constraint: Constraint,
    progress: Callable[[int, str], None] | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Abundances (pixels, endmembers) such that ``X ≈ abundances @ endmembers``,
    and each pixel's RMS residual.

    NONE is ordinary least squares; SUM_TO_ONE adds the equality constraint
    exactly; FULLY_CONSTRAINED also keeps abundances non-negative (FCLS,
    solved for all pixels at once by ADMM).
    """
    data = np.asarray(X, dtype=np.float64)
    E = np.asarray(endmembers, dtype=np.float64)
    m = E.shape[0]
    abundances = np.full((data.shape[0], m), np.nan)
    rmse = np.full(data.shape[0], np.nan)
    good = np.flatnonzero(_finiteRows(data))
    solve = {
        Constraint.NONE: _leastSquares,
        Constraint.SUM_TO_ONE: _sumToOne,
        Constraint.FULLY_CONSTRAINED: _fullyConstrained,
    }[constraint]
    for start in range(0, good.size, _CHUNK):
        rows = good[start : start + _CHUNK]
        block = data[rows]
        a = solve(block, E)
        abundances[rows] = a
        residual = block - a @ E
        rmse[rows] = np.sqrt(np.mean(residual**2, axis=1))
        if progress is not None:
            done = min(start + _CHUNK, good.size)
            progress(int(100 * done / good.size), f"{done:,} of {good.size:,} pixels")
    return abundances, rmse


def _leastSquares(X: np.ndarray, E: np.ndarray) -> np.ndarray:
    return np.linalg.lstsq(E.T, X.T, rcond=None)[0].T


def _sumToOne(X: np.ndarray, E: np.ndarray) -> np.ndarray:
    """Equality-constrained least squares via the KKT correction of OLS."""
    gramInv = np.linalg.pinv(E @ E.T)
    ones = np.ones(E.shape[0])
    a = X @ E.T @ gramInv
    correction = (1.0 - a.sum(axis=1)) / (ones @ gramInv @ ones)
    return a + correction[:, None] * (gramInv @ ones)[None, :]


def _fullyConstrained(X: np.ndarray, E: np.ndarray) -> np.ndarray:
    if E.shape[0] <= _EXACT_MAX_ENDMEMBERS:
        return _fullyConstrainedExact(X, E)
    return _fullyConstrainedAdmm(X, E)


def _fullyConstrainedExact(X: np.ndarray, E: np.ndarray) -> np.ndarray:
    """Exact least squares over the probability simplex. The optimum lies on
    some face, where it equals the sum-to-one least-squares solution on that
    face's endmembers; so solve that on every support set and keep, per
    pixel, the feasible (non-negative) solution with the smallest residual."""
    n, m = X.shape[0], E.shape[0]
    gram = E @ E.T
    B = X @ E.T  # (pixels, m)
    best = np.full(n, np.inf)
    out = np.zeros((n, m))
    for mask in range(1, 2**m):
        support = np.array([j for j in range(m) if mask >> j & 1], dtype=np.intp)
        gramInv = np.linalg.pinv(gram[np.ix_(support, support)])
        w = gramInv.sum(axis=1)  # G⁻¹ 1
        u = B[:, support] @ gramInv.T  # G⁻¹ b per pixel
        a = u + ((1.0 - u.sum(axis=1)) / w.sum())[:, None] * w[None, :]
        feasible = np.all(a >= -1e-10, axis=1)
        # ‖x - Eᵀa‖² up to the constant ‖x‖²: aᵀGa - 2aᵀb
        cost = np.einsum(
            "ij,jk,ik->i", a, gram[np.ix_(support, support)], a
        ) - 2.0 * np.einsum("ij,ij->i", a, B[:, support])
        better = feasible & (cost < best)
        best[better] = cost[better]
        rows = np.flatnonzero(better)
        out[rows] = 0.0
        out[np.ix_(rows, support)] = np.clip(a[better], 0.0, None)
    return out


def _fullyConstrainedAdmm(X: np.ndarray, E: np.ndarray) -> np.ndarray:
    """Least squares over the probability simplex (non-negative, summing to
    one), by ADMM vectorized across pixels: minimize ½‖Eᵀa - x‖² subject to
    a = z with z on the simplex (exact Euclidean projection)."""
    m = E.shape[0]
    gram = E @ E.T
    eigenvalues = np.linalg.eigvalsh(gram)
    # penalty at the geometric mean of the extreme curvatures: converges fast
    # even when endmembers are similar (an ill-conditioned Gram matrix)
    rho = max(float(np.sqrt(max(eigenvalues[0], 1e-12) * eigenvalues[-1])), 1e-12)
    factor = np.linalg.inv(gram + rho * np.eye(m))
    EtX = X @ E.T  # (pixels, m)
    z = _projectToSimplex(_sumToOne(X, E))
    u = np.zeros_like(z)
    for _ in range(_ADMM_ITERATIONS):
        a = (EtX + rho * (z - u)) @ factor.T
        zNew = _projectToSimplex(a + u)
        u += a - zNew
        converged = max(np.max(np.abs(zNew - z)), np.max(np.abs(a - zNew))) < 1e-6
        z = zNew
        if converged:
            break
    return z


def _projectToSimplex(V: np.ndarray) -> np.ndarray:
    """Row-wise Euclidean projection onto {a : a ≥ 0, Σa = 1} (Duchi et al. 2008)."""
    m = V.shape[1]
    sortedDesc = -np.sort(-V, axis=1)
    cumulative = np.cumsum(sortedDesc, axis=1) - 1.0
    ranks = np.arange(1, m + 1)
    positive = sortedDesc - cumulative / ranks > 0
    rho = m - 1 - np.argmax(positive[:, ::-1], axis=1)  # last True index
    theta = cumulative[np.arange(V.shape[0]), rho] / (rho + 1)
    return np.clip(V - theta[:, None], 0.0, None)


def mixtureTunedMatchedFilter(
    X: np.ndarray, targets: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """MTMF (Boardman 1998) for data in noise-whitened (MNF) space, where the
    noise covariance is the identity.

    Matched filter score: each pixel's estimated abundance of each target
    (0 = background, 1 = pure target), from the filter that suppresses the
    background covariance. Infeasibility: how far the pixel is, in noise
    sigmas, from where a mixture of background and that much target would
    lie; the covariance shrinks from the background's at MF 0 to the noise's
    at MF 1. Good detections have a high MF score and low infeasibility.

    Returns (mf, infeasibility), each (pixels, targets).
    """
    data = np.asarray(X, dtype=np.float64)
    T = np.asarray(targets, dtype=np.float64)
    good = np.flatnonzero(_finiteRows(data))
    mf = np.full((data.shape[0], T.shape[0]), np.nan)
    infeasibility = np.full_like(mf, np.nan)
    if good.size < 2:
        return mf, infeasibility
    mean = data[good].mean(axis=0)
    centred = data[good] - mean
    covariance = centred.T @ centred / (good.size - 1)
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    eigenvalues = np.maximum(eigenvalues, 1e-12)
    for j, target in enumerate(T):
        d = target - mean
        dRot = eigenvectors.T @ d
        weights = eigenvectors @ (dRot / eigenvalues)  # C⁻¹ d
        weights /= d @ weights
        for start in range(0, good.size, _CHUNK):
            rows = good[start : start + _CHUNK]
            c = data[rows] - mean
            score = c @ weights
            residual = (c - score[:, None] * d[None, :]) @ eigenvectors
            variance = (1.0 - score[:, None]) ** 2 * eigenvalues + score[:, None] ** 2
            mf[rows, j] = score
            infeasibility[rows, j] = np.sqrt(np.sum(residual**2 / variance, axis=1))
    return mf, infeasibility
