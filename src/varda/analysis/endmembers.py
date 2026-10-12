"""Endmember extraction: pixel purity index and n-D projection helpers.

Pure numpy. Data are (pixels, dims) matrices, usually the leading MNF
components of an image.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
from scipy.cluster.vq import kmeans2

# (percent 0-100, message)
ProgressCallback = Callable[[int, str], None]

# Memory budget for one batch of projections (pixels x skewers float64)
_BATCH_BYTES = 64 * 2**20


def pixelPurityIndex(
    X: np.ndarray,
    iterations: int = 10_000,
    threshold: float = 2.5,
    *,
    seed: int | None = None,
    start: np.ndarray | None = None,
    progress: ProgressCallback | None = None,
) -> np.ndarray:
    """Pixel purity index (Boardman et al. 1995): project every pixel onto
    ``iterations`` random unit vectors ("skewers") and count, per pixel, how
    often it lands within ``threshold`` (data units) of either end of a
    projection. Pure pixels sit at the corners of the data cloud and score
    high; mixtures score 0.

    ``start`` continues from earlier counts. Rows with a non-finite value
    score 0. Returns int64 counts, one per row.
    """
    report = progress or (lambda percent, message: None)
    data = np.asarray(X, dtype=np.float64)
    n, dims = data.shape
    counts = (
        np.zeros(n, dtype=np.int64)
        if start is None
        else np.array(start, dtype=np.int64)
    )
    good = np.flatnonzero(np.all(np.isfinite(data), axis=1))
    if good.size == 0 or iterations <= 0:
        report(100, "done")
        return counts
    Xg = data[good]
    rng = np.random.default_rng(seed)
    batch = max(1, min(iterations, _BATCH_BYTES // (8 * good.size)))
    done = 0
    hits = np.zeros(good.size, dtype=np.int64)
    while done < iterations:
        m = min(batch, iterations - done)
        skewers = rng.normal(size=(dims, m))
        skewers /= np.linalg.norm(skewers, axis=0)
        projected = Xg @ skewers  # (pixels, m)
        low = projected.min(axis=0)
        high = projected.max(axis=0)
        extreme = (projected <= low + threshold) | (projected >= high - threshold)
        hits += extreme.sum(axis=1)
        done += m
        report(int(100 * done / iterations), f"{done} of {iterations} skewers")
    counts[good] += hits
    return counts


def randomPlane(dims: int, rng: np.random.Generator) -> np.ndarray:
    """A random orthonormal (dims, 2) basis of a plane in ``dims``-D space."""
    q, _ = np.linalg.qr(rng.normal(size=(dims, 2)))
    return q[:, :2]


def interpolatePlane(a: np.ndarray, b: np.ndarray, t: float) -> np.ndarray:
    """The plane a fraction ``t`` of the way from plane ``a`` to plane ``b``
    along the geodesic between them (a grand tour step). Returns an
    orthonormal (dims, 2) basis equal to ``a`` at t = 0 and spanning ``b`` at
    t = 1; small steps in ``t`` move the projection smoothly."""
    # Principal vectors: rotate each basis so the pair (a_i, b_i) are the
    # closest directions of the two planes, then turn a_i towards b_i.
    u, cosines, vt = np.linalg.svd(a.T @ b)
    aRot = a @ u
    bRot = b @ vt.T
    out = np.empty_like(a)
    for i in range(2):
        theta = float(np.arccos(np.clip(cosines[i], -1.0, 1.0)))
        if theta < 1e-9:
            out[:, i] = aRot[:, i]
            continue
        # unit vector in the plane of (a_i, b_i), orthogonal to a_i
        orth = bRot[:, i] - cosines[i] * aRot[:, i]
        orth /= np.linalg.norm(orth)
        out[:, i] = np.cos(t * theta) * aRot[:, i] + np.sin(t * theta) * orth
    # express in a's original orientation so t = 0 returns a exactly
    return out @ u.T


def suggestGroups(X: np.ndarray, groups: int, *, seed: int = 0) -> np.ndarray:
    """k-means labels (0..groups-1) for the rows of ``X``: a starting point
    for endmember classes in the n-D view."""
    data = np.asarray(X, dtype=np.float64)
    if data.shape[0] < groups or groups < 1:
        raise ValueError(f"Need at least {groups} points to suggest {groups} groups")
    _, labels = kmeans2(data, groups, minit="++", seed=seed)
    return labels.astype(np.intp)
