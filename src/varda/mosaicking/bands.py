"""Which bands of a spectral cube to align on.

A band helps matching when it shows the scene's texture clearly over its
noise. Each band's noise is estimated from differences between neighboring
pixels (as MNF estimates noise): the scene changes little from one pixel to
the next, so what's left is mostly noise. The SNR is the band's scene
contrast (its standard deviation, less the noise) over that noise. The best
bands are taken from across the spectrum, so an atmospheric band or a
detector artifact in one region can't decide the fit alone.
"""

from __future__ import annotations

import numpy as np

DEFAULT_BAND_COUNT = 5


def bandSnr(cube: np.ndarray) -> np.ndarray:
    """Each band's SNR (scene contrast over noise) in a (rows, cols, bands)
    cube; NaN pixels are left out. 0 for a band without contrast."""
    cube = np.asarray(cube, dtype=np.float64)
    snr = np.zeros(cube.shape[2])
    for band in range(cube.shape[2]):
        values = cube[:, :, band]
        differences = np.concatenate(
            [
                (values[:, 1:] - values[:, :-1]).ravel(),
                (values[1:, :] - values[:-1, :]).ravel(),
            ]
        )
        differences = differences[np.isfinite(differences)]
        finite = values[np.isfinite(values)]
        if differences.size < 2 or finite.size < 2:
            continue
        # A robust spread (MAD), so edges don't count as noise; a difference
        # of two pixels has twice a pixel's noise variance
        mad = np.median(np.abs(differences - np.median(differences)))
        noise = 1.4826 * mad / np.sqrt(2.0)
        signal = np.sqrt(max(float(np.var(finite)) - noise**2, 0.0))
        snr[band] = signal / noise if noise > 0 else (np.inf if signal > 0 else 0.0)
    return snr


def chooseBands(
    snr: np.ndarray,
    wavelengths: np.ndarray | None,
    count: int = DEFAULT_BAND_COUNT,
    badBands: np.ndarray | None = None,
) -> list[int]:
    """The ``count`` bands to align on: the usable range (good bands with a
    finite, positive SNR) is split into ``count`` equal wavelength intervals,
    and the band with the best SNR is taken from each. Band indices, sorted."""
    snr = np.asarray(snr, dtype=np.float64)
    usable = np.isfinite(snr) & (snr > 0)
    if badBands is not None and len(badBands):
        usable &= ~np.asarray(badBands, bool)
    candidates = np.flatnonzero(usable)
    if candidates.size <= count:
        return [int(i) for i in candidates]
    position = (
        np.asarray(wavelengths, dtype=np.float64)[candidates]
        if wavelengths is not None
        else candidates.astype(np.float64)
    )
    edges = np.linspace(position.min(), position.max(), count + 1)
    region = np.clip(np.searchsorted(edges, position, side="right") - 1, 0, count - 1)
    chosen = []
    for r in range(count):
        members = candidates[region == r]
        if members.size:
            chosen.append(int(members[np.argmax(snr[members])]))
    # An empty interval (a gap in the bands) gives its turn to the next best
    rest = [int(i) for i in candidates[np.argsort(-snr[candidates])] if i not in chosen]
    return sorted(chosen + rest[: count - len(chosen)])
