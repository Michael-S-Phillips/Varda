"""Spatial-spectral patches: the square neighbourhood of a pixel, all bands.

The training/prediction unit for the CNN and ViT classifiers. Patches are
(size, size, bands) with the pixel at the centre; the cube is reflect-padded
so border pixels get full patches. Whole-image prediction goes through
``iterPatchChunks`` so the full (pixels x size² x bands) array — tens of GB for
a CRISM cube — is never materialised.
"""

from __future__ import annotations

from collections.abc import Iterator

import numpy as np


def extractPatches(
    cube: np.ndarray, rows: np.ndarray, cols: np.ndarray, size: int
) -> np.ndarray:
    """(n, size, size, bands) patches centred on the given pixels."""
    half = size // 2
    padded = np.pad(
        np.asarray(cube), ((half, half), (half, half), (0, 0)), mode="reflect"
    )
    return _patchesFromPadded(padded, np.asarray(rows), np.asarray(cols), size)


def iterPatchChunks(
    cube: np.ndarray, valid: np.ndarray, size: int, chunkPixels: int = 4096
) -> Iterator[tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """Yield (rows, cols, patches) for every valid pixel in row-major order,
    at most ``chunkPixels`` pixels per chunk."""
    half = size // 2
    padded = np.pad(
        np.asarray(cube), ((half, half), (half, half), (0, 0)), mode="reflect"
    )
    coordinates = np.argwhere(valid)
    for start in range(0, coordinates.shape[0], chunkPixels):
        chunk = coordinates[start : start + chunkPixels]
        rows, cols = chunk[:, 0], chunk[:, 1]
        yield rows, cols, _patchesFromPadded(padded, rows, cols, size)


def _patchesFromPadded(
    padded: np.ndarray, rows: np.ndarray, cols: np.ndarray, size: int
) -> np.ndarray:
    half = size // 2
    offsets = np.arange(-half, half + 1)
    rowIndex = rows[:, None, None] + half + offsets[None, :, None]
    colIndex = cols[:, None, None] + half + offsets[None, None, :]
    return padded[rowIndex, colIndex, :]
