"""Make a reference spectrum comparable to one already on a plot.

Library spectra arrive in their own wavelength unit and reflectance scale, so
dropping one onto a plot of scene spectra usually lands it off-screen. These
helpers bring it onto the reference curve: same wavelength unit, and a Y
scale/offset that lays it over the reference within the visible window.
"""

from __future__ import annotations

import numpy as np


def harmonizeWavelengthUnits(x: np.ndarray, referenceX: np.ndarray) -> np.ndarray:
    """Express ``x`` in the unit of ``referenceX``.

    The only mismatch that occurs in practice is micrometres vs nanometres, so
    a median ratio near 1000 either way triggers the conversion.
    """
    ratio = np.nanmedian(referenceX) / np.nanmedian(x)
    if ratio > 100.0:
        return x * 1000.0
    if ratio < 0.01:
        return x / 1000.0
    return x


def matchToReference(
    x: np.ndarray,
    y: np.ndarray,
    referenceX: np.ndarray,
    referenceY: np.ndarray,
    visibleX: tuple[float, float],
) -> tuple[float, float]:
    """Scale and offset that lay ``y`` over ``referenceY`` in the visible window.

    Returns ``(scale, offset)`` such that ``y * scale + offset`` spans the same
    min..max as the reference where both are visible. A curve with fewer than
    two visible samples falls back to its full extent; a flat curve is centred
    on the reference rather than scaled.
    """
    reference = _span(referenceX, referenceY, visibleX)
    current = _span(x, y, visibleX)
    if reference is None or current is None:
        return 1.0, 0.0
    refMin, refMax = reference
    curMin, curMax = current
    if curMax <= curMin:
        return 1.0, (refMin + refMax) / 2.0 - curMin
    scale = (refMax - refMin) / (curMax - curMin) if refMax > refMin else 1.0
    return scale, refMin - curMin * scale


def _span(
    x: np.ndarray, y: np.ndarray, visibleX: tuple[float, float]
) -> tuple[float, float] | None:
    """(min, max) of the finite ``y`` samples within ``visibleX``, else of all."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    finite = np.isfinite(x) & np.isfinite(y)
    if not finite.any():
        return None
    visible = finite & (x >= visibleX[0]) & (x <= visibleX[1])
    mask = visible if np.count_nonzero(visible) >= 2 else finite
    return float(np.min(y[mask])), float(np.max(y[mask]))
