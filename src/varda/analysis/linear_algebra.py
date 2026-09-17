"""Pure-numpy linear transforms of image cubes: PCA, MNF and FastICA.

Cubes are (rows, cols, bands). Work happens on the (samples, bands) matrix of
valid pixels; ``flattenValid``/``unflatten`` convert to and from it, leaving
nodata pixels as NaN in results. Covariances are accumulated in row chunks so
a full CRISM cube (hundreds of thousands of pixels x hundreds of bands) never
needs a second full-size copy.
"""

from __future__ import annotations

import attrs
import numpy as np

_CHUNK_ROWS = 65_536


@attrs.frozen
class TransformResult:
    """``scores``: (samples, k) transformed data. ``loadings``: (bands, k)
    component vectors in band space. ``explainedVariance``: (k,) each
    component's share (of variance for PCA/ICA whitening, of noise-whitened
    variance for MNF), in decreasing order."""

    scores: np.ndarray
    loadings: np.ndarray
    explainedVariance: np.ndarray


def flattenValid(cube, nodata: float | None) -> tuple[np.ndarray, np.ndarray]:
    """(samples, bands) matrix of pixels valid in every band, and the (rows,
    cols) mask of which pixels those are. Nodata and NaN mark invalid."""
    data = np.asarray(cube, dtype=np.float64)
    if nodata is not None:
        data = np.where(data == nodata, np.nan, data)
    valid = np.all(np.isfinite(data), axis=2)
    return data[valid], valid


def unflatten(
    values: np.ndarray, valid: np.ndarray, fill: float = np.nan
) -> np.ndarray:
    """Put (samples, k) values back on the (rows, cols) grid; invalid pixels get ``fill``."""
    out = np.full(valid.shape + (values.shape[1],), fill, dtype=np.float64)
    out[valid] = values
    return out


def pca(X: np.ndarray, components: int) -> TransformResult:
    """Principal components of the rows of ``X``, most variance first."""
    n, bands = X.shape
    k = min(components, bands)
    if n < 2 or n < k:
        raise ValueError(f"PCA needs at least {max(k, 2)} samples, got {n}")
    mean = X.mean(axis=0)
    covariance = _covariance(X, mean)
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)  # ascending
    order = np.argsort(eigenvalues)[::-1][:k]
    eigenvalues, eigenvectors = eigenvalues[order], eigenvectors[:, order]
    total = float(np.trace(covariance))
    share = eigenvalues / total if total > 0 else np.zeros(k)
    return TransformResult(
        scores=_project(X, mean, eigenvectors),
        loadings=eigenvectors,
        explainedVariance=share,
    )


def noiseCovariance(cube, valid: np.ndarray) -> np.ndarray:
    """Noise covariance estimated from differences between horizontally
    adjacent valid pixels (Green et al. 1988): the scene is assumed smooth at
    that scale, so the differences are dominated by noise."""
    data = np.asarray(cube, dtype=np.float64)
    pairs = valid[:, 1:] & valid[:, :-1]
    differences = (data[:, 1:, :] - data[:, :-1, :])[pairs] / np.sqrt(2.0)
    if differences.shape[0] < 2:
        raise ValueError("Too few adjacent valid pixels to estimate noise")
    return _covariance(differences, differences.mean(axis=0))


def mnf(X: np.ndarray, noiseCov: np.ndarray, components: int) -> TransformResult:
    """Minimum Noise Fraction: PCA of the noise-whitened data, so components
    are ordered by signal-to-noise rather than by variance."""
    noiseValues, noiseVectors = np.linalg.eigh(noiseCov)
    floor = max(noiseValues.max(), 1e-300) * 1e-10  # guard near-singular noise
    whitening = (
        noiseVectors @ np.diag(np.maximum(noiseValues, floor) ** -0.5) @ noiseVectors.T
    )
    whitened = pca((X - X.mean(axis=0)) @ whitening, components)
    return TransformResult(
        scores=whitened.scores,
        loadings=whitening @ whitened.loadings,
        explainedVariance=whitened.explainedVariance,
    )


def fastIca(
    X: np.ndarray,
    components: int,
    maxIterations: int = 200,
    tolerance: float = 1e-5,
    seed: int = 0,
) -> tuple[np.ndarray, np.ndarray]:
    """FastICA (parallel, logcosh contrast) on PCA-whitened data.

    Returns unit-variance independent sources (samples, k) and the mixing
    matrix in band space (bands, k) such that ``X - mean ~ sources @ mixing.T``.
    """
    n = X.shape[0]
    whitened = pca(X, components)
    k = whitened.scores.shape[1]
    Z = whitened.scores / np.sqrt(whitened.scores.var(axis=0, ddof=1))

    rng = np.random.default_rng(seed)
    W = _symmetricDecorrelation(rng.normal(size=(k, k)))
    for _ in range(maxIterations):
        WZ = Z @ W.T
        g = np.tanh(WZ)
        gDerivativeMean = (1.0 - g**2).mean(axis=0)
        Wnew = _symmetricDecorrelation((g.T @ Z) / n - gDerivativeMean[:, None] * W)
        converged = np.max(np.abs(np.abs(np.diag(Wnew @ W.T)) - 1.0)) < tolerance
        W = Wnew
        if converged:
            break

    sources = Z @ W.T
    mixing, *_ = np.linalg.lstsq(sources, X - X.mean(axis=0), rcond=None)
    return sources, mixing.T


def _symmetricDecorrelation(W: np.ndarray) -> np.ndarray:
    values, vectors = np.linalg.eigh(W @ W.T)
    return (vectors @ np.diag(values**-0.5) @ vectors.T) @ W


def _covariance(X: np.ndarray, mean: np.ndarray) -> np.ndarray:
    bands = X.shape[1]
    total = np.zeros((bands, bands))
    for start in range(0, X.shape[0], _CHUNK_ROWS):
        chunk = X[start : start + _CHUNK_ROWS] - mean
        total += chunk.T @ chunk
    return total / (X.shape[0] - 1)


def _project(X: np.ndarray, mean: np.ndarray, vectors: np.ndarray) -> np.ndarray:
    scores = np.empty((X.shape[0], vectors.shape[1]))
    for start in range(0, X.shape[0], _CHUNK_ROWS):
        scores[start : start + _CHUNK_ROWS] = (
            X[start : start + _CHUNK_ROWS] - mean
        ) @ vectors
    return scores
