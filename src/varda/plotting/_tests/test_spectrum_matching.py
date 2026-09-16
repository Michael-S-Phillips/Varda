"""Pure-numpy helpers that make a reference spectrum comparable to a plotted one."""

import numpy as np

from varda.plotting.spectrum_matching import harmonizeWavelengthUnits, matchToReference


def test_micrometre_wavelengths_are_converted_to_a_nanometre_reference():
    x = np.linspace(0.35, 2.5, 5)
    referenceX = np.linspace(1000.0, 2600.0, 5)
    np.testing.assert_allclose(harmonizeWavelengthUnits(x, referenceX), x * 1000.0)


def test_nanometre_wavelengths_are_converted_to_a_micrometre_reference():
    x = np.linspace(350.0, 2500.0, 5)
    referenceX = np.linspace(1.0, 2.6, 5)
    np.testing.assert_allclose(harmonizeWavelengthUnits(x, referenceX), x / 1000.0)


def test_comparable_wavelengths_are_left_alone():
    x = np.linspace(350.0, 2500.0, 5)
    referenceX = np.linspace(1000.0, 2600.0, 5)
    np.testing.assert_array_equal(harmonizeWavelengthUnits(x, referenceX), x)


def _spanWithin(x, y, lo, hi):
    mask = (x >= lo) & (x <= hi)
    return float(np.min(y[mask])), float(np.max(y[mask]))


def test_match_maps_curve_span_onto_reference_span_within_visible_range():
    referenceX = np.linspace(1000.0, 2600.0, 161)
    referenceY = np.linspace(0.2, 0.6, 161)
    x = np.linspace(350.0, 2500.0, 431)
    y = 5.0 + 2.0 * np.sin(x / 300.0)
    visible = (1500.0, 2000.0)

    scale, offset = matchToReference(x, y, referenceX, referenceY, visible)

    matched = y * scale + offset
    np.testing.assert_allclose(
        _spanWithin(x, matched, *visible), _spanWithin(referenceX, referenceY, *visible)
    )


def test_curve_with_nothing_visible_falls_back_to_its_full_extent():
    referenceX = np.linspace(1000.0, 2600.0, 17)
    referenceY = np.linspace(0.0, 1.0, 17)
    x = np.linspace(350.0, 900.0, 12)  # entirely outside the visible window
    y = np.linspace(10.0, 20.0, 12)
    visible = (1500.0, 2000.0)

    scale, offset = matchToReference(x, y, referenceX, referenceY, visible)

    # the whole curve is laid over the reference's *visible* span
    matched = y * scale + offset
    np.testing.assert_allclose(
        (matched.min(), matched.max()), _spanWithin(referenceX, referenceY, *visible)
    )


def test_match_centres_a_flat_curve_on_the_reference_without_scaling():
    referenceX = np.linspace(1000.0, 2600.0, 17)
    referenceY = np.linspace(0.2, 0.6, 17)
    x = np.linspace(1000.0, 2600.0, 17)
    y = np.full(17, 7.0)

    scale, offset = matchToReference(x, y, referenceX, referenceY, (1000.0, 2600.0))

    assert scale == 1.0
    np.testing.assert_allclose(7.0 * scale + offset, 0.4)


def test_match_ignores_nan_samples():
    referenceX = np.linspace(1000.0, 2600.0, 17)
    referenceY = np.linspace(0.0, 1.0, 17)
    x = np.linspace(1000.0, 2600.0, 17)
    y = np.linspace(0.0, 2.0, 17)
    y[3] = np.nan

    scale, offset = matchToReference(x, y, referenceX, referenceY, (1000.0, 2600.0))

    np.testing.assert_allclose(scale, 0.5)
    np.testing.assert_allclose(offset, 0.0)
