"""The plain parts of a mosaic recipe (no dependencies on the rest of the
mosaic code):

- a radiometric ``Correction`` of one input: a gain and offset per band
  (documented linear corrections, as science mosaics use), or a per-band
  lookup table from histogram matching (visual only: it changes spectral
  shape);
- a ``Seam`` between two overlapping inputs: where the lower one takes over.

Both are applied while rendering, so the inputs are never changed."""

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


class SeamMethod(LabeledEnum):
    PRIORITY = "Priority (the stack order)"
    VORONOI = "Middle of each overlap (Voronoi)"
    LEAST_DIFFERENCE = "Least difference (where the images agree)"


@frozen(eq=False)
class Seam:
    """Where, in the overlap of two inputs, the lower one (``bottom``) takes
    over from the upper one (``top``): polygons in map coordinates. Elsewhere
    the stack order decides."""

    top: int  # input keys
    bottom: int
    regions: tuple[np.ndarray, ...]  # each (N, 2) map coordinates

    def state(self) -> dict:
        return {
            "top": self.top,
            "bottom": self.bottom,
            "regions": [r.tolist() for r in self.regions],
        }

    @classmethod
    def fromState(cls, state: dict) -> Seam:
        return cls(
            int(state["top"]),
            int(state["bottom"]),
            tuple(np.asarray(r, float) for r in state["regions"]),
        )
