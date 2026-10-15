"""A radiometric correction of one mosaic input: a gain and offset per band
(documented linear corrections, as science mosaics use), or a per-band
lookup table from histogram matching (visual only: it changes spectral
shape). Applied while rendering, so the inputs are never changed."""

from __future__ import annotations

import numpy as np
from attrs import frozen

from varda.common.parameter import LabeledEnum


class RadiometryMethod(LabeledEnum):
    NONE = "None (keeps values exact)"
    REFERENCE = "Linear, to the held images"
    GLOBAL = "Linear, global least squares (as ISIS equalizer)"
    HISTOGRAM = "Histogram matching (visual only: changes spectral shape)"


class LinearMode(LabeledEnum):
    BOTH = "Gain and offset"
    GAIN = "Gain only"
    OFFSET = "Offset only"


@frozen(eq=False)
class Correction:
    gain: np.ndarray  # (bands,)
    offset: np.ndarray  # (bands,)
    # Histogram matching: per band, input values and what they become
    lutIn: np.ndarray | None = None  # (bands, points), increasing per band
    lutOut: np.ndarray | None = None

    @classmethod
    def identity(cls, bands: int) -> Correction:
        return cls(np.ones(bands), np.zeros(bands))

    def apply(self, values: np.ndarray, bands: list[int] | None = None) -> np.ndarray:
        """Corrected ``values`` (..., bands); ``bands`` says which of the
        image's bands they are (all, by default)."""
        index = slice(None) if bands is None else np.asarray(bands)
        out = np.asarray(values, np.float32) * self.gain[index] + self.offset[index]
        if self.lutIn is not None and self.lutOut is not None:
            lutIn, lutOut = self.lutIn[index], self.lutOut[index]
            for k in range(out.shape[-1]):
                out[..., k] = extendedInterp(out[..., k], lutIn[k], lutOut[k])
        return out.astype(np.float32)

    def state(self) -> dict:
        return {
            "gain": self.gain.tolist(),
            "offset": self.offset.tolist(),
            "lutIn": None if self.lutIn is None else self.lutIn.tolist(),
            "lutOut": None if self.lutOut is None else self.lutOut.tolist(),
        }

    @classmethod
    def fromState(cls, state: dict) -> Correction:
        def array(name: str) -> np.ndarray | None:
            value = state.get(name)
            return None if value is None else np.asarray(value, float)

        return cls(
            np.asarray(state["gain"], float),
            np.asarray(state["offset"], float),
            array("lutIn"),
            array("lutOut"),
        )


def extendedInterp(x: np.ndarray, xp: np.ndarray, fp: np.ndarray) -> np.ndarray:
    """``np.interp``, continued linearly beyond the ends (by the end
    segments' slopes) instead of clamping, so values outside the matched
    range aren't flattened."""
    y = np.interp(x, xp, fp)
    if len(xp) > 1:
        low = (fp[1] - fp[0]) / ((xp[1] - xp[0]) or 1.0)
        high = (fp[-1] - fp[-2]) / ((xp[-1] - xp[-2]) or 1.0)
        y = np.where(x < xp[0], fp[0] + (x - xp[0]) * low, y)
        y = np.where(x > xp[-1], fp[-1] + (x - xp[-1]) * high, y)
    return y
