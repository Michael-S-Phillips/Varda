"""Pure-numpy linear transforms of image cubes: PCA, MNF and FastICA.

Cubes are (rows, cols, bands). Work happens on the (samples, bands) matrix of
valid pixels; ``flattenValid``/``unflatten`` convert to and from it, leaving
nodata pixels as NaN in results. Covariances are accumulated in row chunks so
a full CRISM cube (hundreds of thousands of pixels x hundreds of bands) never
needs a second full-size copy.

Every transform also returns what its inverse needs (``mean`` and ``inverse``),
so the number of components to keep can be decided afterwards, ENVI-style:
transform with everything, look at the eigenvalues and the component images,
then rebuild the image from the first N.
"""

from __future__ import annotations

from collections.abc import Sequence

import attrs
import numpy as np

_CHUNK_ROWS = 65_536

# Fraction of the variance the suggested PCA/ICA component count captures.
_SUGGESTED_VARIANCE = 0.99
# MNF eigenvalues are SNR + 1; components below this are taken to be noise.
_MNF_NOISE_EIGENVALUE = 2.0


@attrs.frozen
class TransformResult:
    """``scores``: (samples, k) transformed data. ``loadings``: (bands, k)
    component vectors in band space. ``explainedVariance``: (k,) each
    component's share (of variance for PCA/ICA, of noise-whitened variance for
    MNF), in decreasing order. ``eigenvalues``: (k,) the unnormalised values
    behind those shares. ``mean``: (bands,) and ``inverse``: (k, bands) such that
    ``data ~ scores @ inverse + mean``."""

    scores: np.ndarray
    loadings: np.ndarray
    explainedVariance: np.ndarray
    eigenvalues: np.ndarray
    mean: np.ndarray
    inverse: np.ndarray


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


def inverseTransform(
    scores: np.ndarray,
    inverse: np.ndarray,
    mean: np.ndarray,
    components: int | Sequence[int],
) -> np.ndarray:
    """Rebuild (samples, bands) data from the first ``components`` scores, or
    from the given 0-based component indices."""
    if isinstance(components, int):
        k = min(components, scores.shape[1], inverse.shape[0])
        return scores[:, :k] @ inverse[:k] + mean
    indices = list(components)
    return scores[:, indices] @ inverse[indices] + mean


def describeComponentSelection(indices: Sequence[int]) -> str:
    """'3 components' for the first three, else the 1-based numbers as ranges,
    e.g. 'components 2-5' or 'components 1, 3-4, 6'."""
    ordered = sorted(set(int(i) for i in indices))
    if ordered == list(range(len(ordered))):
        return f"{len(ordered)} components"
    runs: list[list[int]] = []
    for index in ordered:
        if runs and index == runs[-1][-1] + 1:
            runs[-1].append(index)
        else:
            runs.append([index])
    parts = [
        f"{run[0] + 1}" if len(run) == 1 else f"{run[0] + 1}-{run[-1] + 1}"
        for run in runs
    ]
    noun = "component" if len(ordered) == 1 else "components"
    return f"{noun} {', '.join(parts)}"


def suggestedComponents(eigenvalues: np.ndarray, kind: str) -> int:
    """A starting point for how many components to keep: for MNF, those with
    an eigenvalue clearly above the noise floor; otherwise enough to capture
    99% of the variance. At least one."""
    values = np.asarray(eigenvalues, dtype=np.float64)
    if kind == "MNF":
        return max(1, int(np.sum(values > _MNF_NOISE_EIGENVALUE)))
    total = values.sum()
    if total <= 0:
        return 1
    cumulative = np.cumsum(values) / total
    return int(np.searchsorted(cumulative, _SUGGESTED_VARIANCE) + 1)


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
        eigenvalues=eigenvalues,
        mean=mean,
        inverse=eigenvectors.T,  # orthonormal
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
    noiseValues = np.maximum(noiseValues, floor)
    whitening = noiseVectors @ np.diag(noiseValues**-0.5) @ noiseVectors.T
    unwhitening = noiseVectors @ np.diag(noiseValues**0.5) @ noiseVectors.T
    mean = X.mean(axis=0)
    whitened = pca((X - mean) @ whitening, components)
    return TransformResult(
        scores=whitened.scores,
        loadings=whitening @ whitened.loadings,
        explainedVariance=whitened.explainedVariance,
        eigenvalues=whitened.eigenvalues,
        mean=mean,
        inverse=whitened.loadings.T @ unwhitening,
    )


def fastIca(
    X: np.ndarray,
    components: int,
    maxIterations: int = 200,
    tolerance: float = 1e-5,
    seed: int = 0,
) -> TransformResult:
    """FastICA (parallel, logcosh contrast) on PCA-whitened data.

    ``scores`` are unit-variance independent sources ordered by how much of the
    data's variance each explains; ``loadings`` is the mixing matrix in band
    space (bands, k), so ``X - mean ~ scores @ loadings.T``.
    """
    n = X.shape[0]
    mean = X.mean(axis=0)
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
    mixing, *_ = np.linalg.lstsq(sources, X - mean, rcond=None)  # (k, bands)
    # Unit-variance sources: each one's share of the variance is its mixing
    # vector's squared norm. Order the components by it, largest first.
    variance = np.sum(mixing**2, axis=1)
    order = np.argsort(variance)[::-1]
    sources, mixing, variance = sources[:, order], mixing[order], variance[order]
    total = variance.sum()
    return TransformResult(
        scores=sources,
        loadings=mixing.T,
        explainedVariance=variance / total if total > 0 else np.zeros(k),
        eigenvalues=variance,
        mean=mean,
        inverse=mixing,
    )


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
