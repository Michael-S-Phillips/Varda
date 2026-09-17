"""Spatial-spectral patches around pixels, the training unit for CNN/ViT classifiers."""

import numpy as np

from varda.analysis.patches import extractPatches, iterPatchChunks


def _cube():
    rows, cols = np.indices((6, 7))
    return np.stack([rows.astype(float), cols.astype(float)], axis=2)  # bands: row, col


def test_patch_is_centred_on_the_pixel_with_bands_as_last_axis():
    patches = extractPatches(_cube(), np.array([2]), np.array([3]), size=3)

    assert patches.shape == (1, 3, 3, 2)
    np.testing.assert_array_equal(patches[0, 1, 1], [2.0, 3.0])  # centre = the pixel
    np.testing.assert_array_equal(patches[0, 0, 0], [1.0, 2.0])  # up-left neighbour


def test_patches_at_the_border_are_reflect_padded():
    patches = extractPatches(_cube(), np.array([0]), np.array([0]), size=3)
    # reflect padding mirrors the neighbour row/col (numpy "reflect": ...1,0,1...)
    np.testing.assert_array_equal(patches[0, 0, 0], [1.0, 1.0])
    np.testing.assert_array_equal(patches[0, 1, 1], [0.0, 0.0])


def test_chunks_cover_every_valid_pixel_once_in_row_major_order():
    valid = np.ones((6, 7), dtype=bool)
    valid[0, 0] = False
    chunks = list(iterPatchChunks(_cube(), valid, size=3, chunkPixels=10))

    counts = [patches.shape[0] for _rows, _cols, patches in chunks]
    assert sum(counts) == 41 and max(counts) <= 10
    rows = np.concatenate([r for r, _c, _p in chunks])
    cols = np.concatenate([c for _r, c, _p in chunks])
    expected = np.argwhere(valid)
    np.testing.assert_array_equal(np.column_stack([rows, cols]), expected)
