"""Shared fixtures for ROI tests."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Callable

import numpy as np
import pytest


@pytest.fixture
def make_split_image() -> Callable[[int, int, int, float, float], SimpleNamespace]:
    """Factory for a fake VardaRaster-like image split left/right by fill value.

    The left half (columns < ``width // 2``) is filled with ``left_fill`` and the
    right half with ``right_fill``, across all bands. Supports the windowed
    ``getData`` contract used by ROICollection.
    """

    def _make(
        width: int,
        height: int,
        bands: int,
        left_fill: float,
        right_fill: float,
    ) -> SimpleNamespace:
        data = np.empty((height, width, bands), dtype=np.float64)
        half = width // 2
        data[:, :half, :] = left_fill
        data[:, half:, :] = right_fill
        return SimpleNamespace(
            width=width,
            height=height,
            bandCount=bands,
            nodata=None,
            wavelengths=np.arange(bands, dtype=np.float64),
            wavelengthsType=float,
            getData=lambda bandIndices=None, window=None: (
                data[
                    window[0] : window[0] + window[2],
                    window[1] : window[1] + window[3],
                    :,
                ]
                if window is not None
                else data
            ),
        )

    return _make
