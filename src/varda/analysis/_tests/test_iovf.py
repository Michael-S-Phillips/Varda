"""IOVF: the iterative outlier voting filter removes isolated spikes and keeps
the smooth spectra around them."""

import numpy as np
import pytest

from varda.analysis.iovf import _isStalled, _kernelTables, _pad, _replace, iovfFilter


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


def test_stalled_rounds_stop_the_filter():
    assert not _isStalled([100, 50, 40, 30, 20, 10])
    assert _isStalled([100, 50, 40, 41, 42, 40, 40, 41])  # no net fall over five rounds
    assert not _isStalled([100, 90])


def _replaced(noise: np.ndarray, flagged: list[tuple[int, int, int]]) -> np.ndarray:
    window = (3, 3, 3)
    half = (1, 1, 1)
    out = noise.copy()
    F = np.array(flagged)
    _replace(out, _pad(noise, half), F, window, half, _kernelTables(window), 4.0)
    return out[F[:, 0], F[:, 1], F[:, 2]]


def test_replacement_is_the_weighted_average_of_the_neighbors_left():
    """Flagged and no-data neighbors are ignored (Phillips et al. 2024, 2.2):
    the weights of the neighbors left are renormalized, so an outlier among
    neighbors that all read 0.2 becomes 0.2, not a value pulled toward the
    reference (0)."""
    noise = np.full((5, 5, 5), 0.2)
    noise[2, 2, 2] = 5.0  # the outlier
    noise[2, 2, 3] = -4.0  # a flagged neighbor
    noise[1, 1, 1] = np.nan  # a no-data neighbor
    values = _replaced(noise, [(2, 2, 2), (2, 2, 3)])
    np.testing.assert_allclose(values, 0.2)


def test_an_outlier_with_no_neighbors_left_takes_the_reference():
    noise = np.full((3, 3, 3), np.nan)
    noise[1, 1, 1] = 5.0
    assert _replaced(noise, [(1, 1, 1)])[0] == 0.0  # noise 0: the reference
