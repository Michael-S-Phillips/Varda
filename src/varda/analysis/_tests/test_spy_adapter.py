"""All Spectral Python (SPy) use goes through one adapter, which keeps SPy
quiet and tidy inside Varda."""

import logging

import numpy as np

from varda.analysis import _spy
from varda.analysis.spectral_library import LibrarySpectrum, resampleTo


def test_spy_logs_through_varda_and_shows_no_console_progress():
    assert logging.getLogger("spectral").handlers == []
    assert _spy.spectral.settings.show_progress is False


def test_resampling_to_wide_bands_averages_over_the_band_response():
    """A narrow feature seen by a wide band is diluted, not sampled at its centre."""
    fine = np.arange(1000.0, 3000.0, 1.0)
    reflectance = np.ones_like(fine)
    reflectance[(fine > 1995) & (fine < 2005)] = 0.0  # 10 nm-wide absorption at 2000
    spectrum = LibrarySpectrum("narrow", fine, reflectance)
    centers = np.array([1800.0, 2000.0, 2200.0])
    point = resampleTo(spectrum, centers)
    wide = resampleTo(spectrum, centers, fwhmNm=np.array([50.0, 50.0, 50.0]))
    assert point[1] == 0.0  # point sampling hits the dip
    assert 0.7 < wide[1] < 0.95  # a 50 nm band sees mostly continuum
    np.testing.assert_allclose(wide[[0, 2]], 1.0, atol=1e-6)


def test_resampling_ignores_library_gaps_and_blanks_bands_outside_it():
    fine = np.arange(1000.0, 2500.0, 1.0)
    reflectance = np.full_like(fine, 0.5)
    reflectance[(fine > 1403) & (fine < 1407)] = np.nan  # a gap inside one band
    spectrum = LibrarySpectrum("gappy", fine, reflectance)
    out = resampleTo(
        spectrum, np.array([1405.0, 2400.0, 2600.0]), fwhmNm=np.full(3, 20.0)
    )
    np.testing.assert_allclose(out[:2], 0.5, atol=1e-9)
    assert np.isnan(out[2])
