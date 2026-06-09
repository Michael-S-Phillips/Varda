"""Pure spectral ratio math (Qt-free, unit-tested)."""

from __future__ import annotations

import numpy as np


def computeRatioSpectrum(numerator: np.ndarray, denominator: np.ndarray) -> np.ndarray:
    """Element-wise ratio of two spectra (numerator / denominator).

    Args:
        numerator: Per-band values.
        denominator: Per-band values, same shape as ``numerator``.

    Returns:
        A float64 array the same shape as the inputs. Any band where the
        denominator is zero, or where either operand is NaN, is NaN. No
        exceptions or warnings are raised.
    """
    num = np.asarray(numerator, dtype=np.float64)
    den = np.asarray(denominator, dtype=np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = num / den
    ratio[~np.isfinite(ratio)] = np.nan
    return ratio
