"""IOVF: the iterative outlier voting filter removes isolated spikes and keeps
the smooth spectra around them."""

import numpy as np
import pytest

from varda.analysis.iovf import iovfFilter


def _smoothCube(rows=24, cols=20, bands=60, seed=0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    wl = np.linspace(0.0, 1.0, bands)
    albedo = 0.3 + 0.1 * rng.random((rows, cols, 1))
    shape = 1.0 - 0.2 * np.exp(-0.5 * ((wl - 0.6) / 0.08) ** 2)
    return albedo * shape + 0.002 * rng.normal(size=(rows, cols, bands))


def test_spikes_are_replaced_and_clean_voxels_barely_change():
    clean = _smoothCube()
    spiked = clean.copy()
    rng = np.random.default_rng(1)
    r = rng.integers(3, 21, 40)
    c = rng.integers(3, 17, 40)
    b = rng.integers(10, 50, 40)
    spiked[r, c, b] += 0.5

    result = iovfFilter(spiked, nJobs=1)

    assert result.filtered.shape == clean.shape
    assert np.abs(result.filtered[r, c, b] - clean[r, c, b]).max() < 0.05
    untouched = np.ones(clean.shape, dtype=bool)
    untouched[r, c, b] = False
    assert np.median(np.abs(result.filtered - clean)[untouched]) < 0.003
    assert result.rounds >= 1 and result.replaced[0] >= 40


def test_progress_is_reported_per_round():
    seen = []
    iovfFilter(_smoothCube(), nJobs=1, progress=lambda p, m: seen.append((p, m)))
    assert seen[0][0] == 0 and seen[-1] == (100, "done")
    assert any("round 1" in message for _, message in seen)


def test_threaded_and_serial_runs_agree():
    cube = _smoothCube()
    cube[10, 10, 30] += 0.5
    np.testing.assert_allclose(
        iovfFilter(cube, nJobs=1).filtered, iovfFilter(cube, nJobs=4).filtered
    )


def test_a_cube_smaller_than_the_window_is_rejected():
    with pytest.raises(ValueError, match="smaller than the window"):
        iovfFilter(np.zeros((3, 3, 30)))


def test_nodata_border_filters_like_the_cropped_valid_region():
    """A no-data border (NaN) must be left out of the windows: as zero noise it
    makes every valid voxel along it look like an outlier, round after round.
    Left out, the valid region filters as if it had been cropped (replacements
    beside the border differ slightly: there the kernel keeps its full shape
    with the missing members at zero, instead of being truncated)."""
    clean = _smoothCube(rows=30, cols=30, bands=60)
    clean[15, 20, 30] += 0.5  # one real spike
    bordered = clean.copy()
    bordered[:, :8, :] = np.nan

    withBorder = iovfFilter(bordered, nJobs=1)
    cropped = iovfFilter(clean[:, 8:, :].copy(), nJobs=1)

    assert withBorder.replaced == cropped.replaced
    np.testing.assert_allclose(withBorder.filtered[:, 8:], cropped.filtered, atol=0.003)
    assert np.isnan(withBorder.filtered[:, :8]).all()


def test_stops_once_a_round_replaces_little_compared_with_the_first():
    cube = _smoothCube(rows=30, cols=30, bands=60)
    cube[np.random.default_rng(3).random(cube.shape) < 0.01] += 0.3

    full = iovfFilter(cube, nJobs=1, stopFraction=0.0)
    early = iovfFilter(cube, nJobs=1, stopFraction=0.2)

    assert early.rounds < full.rounds
    assert early.replaced[-1] < 0.2 * early.replaced[0]
    assert all(count >= 0.2 * early.replaced[0] for count in early.replaced[1:-1])
    assert early.replaced == full.replaced[: early.rounds]
