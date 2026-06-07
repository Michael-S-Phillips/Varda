"""Tests for the pure spectral ratio function."""

import numpy as np

from varda.rois.ratio import computeRatioSpectrum


def test_basic_division():
    num = np.array([2.0, 4.0, 6.0])
    den = np.array([1.0, 2.0, 3.0])
    np.testing.assert_array_almost_equal(
        computeRatioSpectrum(num, den), [2.0, 2.0, 2.0]
    )


def test_divide_by_zero_is_nan():
    result = computeRatioSpectrum(np.array([1.0, 2.0]), np.array([0.0, 2.0]))
    assert np.isnan(result[0])
    assert result[1] == 1.0


def test_zero_over_zero_is_nan():
    result = computeRatioSpectrum(np.array([0.0]), np.array([0.0]))
    assert np.isnan(result[0])


def test_nan_operands_propagate():
    result = computeRatioSpectrum(np.array([np.nan, 4.0]), np.array([2.0, np.nan]))
    assert np.isnan(result[0])
    assert np.isnan(result[1])


def test_shape_preserved():
    assert computeRatioSpectrum(np.ones(5), np.ones(5)).shape == (5,)


def test_integer_inputs_promoted_to_float():
    num = np.array([3, 6], dtype=np.int64)
    den = np.array([2, 2], dtype=np.int64)
    np.testing.assert_array_almost_equal(computeRatioSpectrum(num, den), [1.5, 3.0])
