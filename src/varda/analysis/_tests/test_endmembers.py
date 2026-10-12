"""Pixel purity index and n-D projection helpers for endmember extraction."""

import numpy as np
import pytest

from varda.analysis.endmembers import (
    findVertices,
    interpolatePlane,
    pixelPurityIndex,
    randomPlane,
    suggestGroups,
)


def _simplexMixtures(n=3000, seed=0):
    """Pixels mixed from 4 corners in 3-D; the first 4 rows are the pure corners."""
    rng = np.random.default_rng(seed)
    corners = np.array([[0, 0, 0], [10, 0, 0], [0, 10, 0], [0, 0, 10]], dtype=float)
    weights = rng.dirichlet(np.ones(4) * 2, size=n)
    X = weights @ corners + 0.05 * rng.normal(size=(n, 3))
    X[:4] = corners
    return X


def test_ppi_counts_the_pure_corners_most_often():
    X = _simplexMixtures()
    counts = pixelPurityIndex(X, iterations=2000, threshold=0.5, seed=1)

    assert counts.shape == (X.shape[0],)
    assert set(np.argsort(counts)[-4:]) == {0, 1, 2, 3}
    assert np.median(counts) == 0


def test_ppi_can_continue_from_earlier_counts_and_reports_progress():
    X = _simplexMixtures()
    seen = []
    first = pixelPurityIndex(X, iterations=500, threshold=0.5, seed=1)
    more = pixelPurityIndex(
        X,
        iterations=500,
        threshold=0.5,
        seed=2,
        start=first,
        progress=lambda p, m: seen.append(p),
    )
    assert np.all(more >= first) and more.sum() > first.sum()
    assert seen[-1] == 100


def test_ppi_ignores_rows_with_missing_values():
    X = _simplexMixtures()
    X[10] = np.nan
    counts = pixelPurityIndex(X, iterations=200, threshold=0.5, seed=0)
    assert counts[10] == 0


def test_random_plane_is_orthonormal():
    plane = randomPlane(6, np.random.default_rng(0))
    assert plane.shape == (6, 2)
    np.testing.assert_allclose(plane.T @ plane, np.eye(2), atol=1e-12)


def test_interpolated_planes_move_smoothly_between_ends():
    rng = np.random.default_rng(0)
    a, b = randomPlane(5, rng), randomPlane(5, rng)
    np.testing.assert_allclose(interpolatePlane(a, b, 0.0), a, atol=1e-12)
    end = interpolatePlane(a, b, 1.0)
    # same plane as b (the basis may rotate within it)
    np.testing.assert_allclose(end @ end.T, b @ b.T, atol=1e-9)
    mid = interpolatePlane(a, b, 0.5)
    np.testing.assert_allclose(mid.T @ mid, np.eye(2), atol=1e-12)
    step = np.abs(interpolatePlane(a, b, 0.51) - mid).max()
    assert step < 0.05


def test_find_vertices_picks_the_simplex_corners():
    X = _simplexMixtures()
    assert set(findVertices(X, 4)) == {0, 1, 2, 3}


def test_suggest_groups_keeps_only_pixels_near_the_corners():
    rng = np.random.default_rng(0)
    corners = np.array([[0, 0], [10, 0], [0, 10]], dtype=float)
    tight = np.vstack([c + 0.2 * rng.normal(size=(20, 2)) for c in corners])
    mixed = rng.dirichlet(np.ones(3), size=200) @ corners  # interior mixtures
    X = np.vstack([tight, mixed])
    labels = suggestGroups(X, 3)

    assert labels.shape == (X.shape[0],)
    for block in range(3):
        group = labels[block * 20 : (block + 1) * 20]
        assert len(set(group)) == 1 and group[0] >= 0
    assert len({labels[0], labels[20], labels[40]}) == 3
    interior = labels[60:]
    assert np.mean(interior == -1) > 0.8  # mixtures stay unassigned


def test_suggest_groups_needs_enough_points():
    with pytest.raises(ValueError):
        suggestGroups(np.zeros((2, 3)), 3)


def test_interpolating_between_spans_of_the_same_plane_stays_finite():
    """With only two dimensions every plane is the same one; rounding can leave
    a tiny angle whose orthogonal direction has zero length."""
    rng = np.random.default_rng(0)
    for _ in range(200):
        a, b = randomPlane(2, rng), randomPlane(2, rng)
        for t in (0.3, 1.0):
            out = interpolatePlane(a, b, t)
            assert np.isfinite(out).all()
            np.testing.assert_allclose(out.T @ out, np.eye(2), atol=1e-9)
