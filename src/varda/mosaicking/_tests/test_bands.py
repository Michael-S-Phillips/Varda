"""Alignment uses the bands with the most scene contrast over noise, spread
across the spectrum."""

import numpy as np

from varda.mosaicking.bands import bandSnr, chooseBands


def _cube(noise: np.ndarray, seed: int = 0) -> np.ndarray:
    """A smooth scene in every band, each band with its own noise level."""
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[:80, :80]
    scene = np.sin(xx / 7.0) + np.cos(yy / 5.0)
    return np.stack(
        [scene + rng.normal(scale=s, size=scene.shape) for s in noise], axis=2
    )


def test_snr_falls_as_noise_rises():
    snr = bandSnr(_cube(np.array([0.01, 0.1, 1.0])))
    assert snr[0] > snr[1] > snr[2]
    assert 5 < snr[1] < 50  # the scene's std is about 1, the noise 0.1


def test_snr_ignores_missing_pixels():
    cube = _cube(np.array([0.05, 0.05]))
    cube[:10, :, 1] = np.nan
    snr = bandSnr(cube)
    assert np.isfinite(snr).all()
    assert abs(snr[0] - snr[1]) / snr[0] < 0.3


def test_a_flat_band_has_no_snr():
    cube = _cube(np.array([0.05]))
    cube = np.concatenate([cube, np.full((80, 80, 1), 3.0)], axis=2)
    assert bandSnr(cube)[1] == 0


def test_the_best_bands_are_chosen_across_the_spectrum():
    wavelengths = np.linspace(1000, 2500, 30)
    snr = np.ones(30)
    snr[[2, 3, 12, 13, 25]] = [5, 9, 7, 6, 8]  # one strong band per region
    chosen = chooseBands(snr, wavelengths, count=3)
    assert chosen == [3, 12, 25]


def test_bad_and_unusable_bands_are_skipped():
    wavelengths = np.linspace(1000, 2500, 10)
    snr = np.arange(10, dtype=float)
    snr[8] = np.nan
    bad = np.zeros(10, bool)
    bad[9] = True
    assert chooseBands(snr, wavelengths, count=1, badBands=bad) == [7]


def test_fewer_bands_than_asked_returns_them_all():
    assert chooseBands(np.array([2.0, 1.0]), np.array([500.0, 600.0]), count=5) == [
        0,
        1,
    ]


def test_a_grayscale_image_uses_its_band():
    assert chooseBands(np.array([3.0]), None, count=5) == [0]
