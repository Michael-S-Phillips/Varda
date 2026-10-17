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


def _jsonList(values: np.ndarray) -> list[float | None]:
    """An array as a list, NaN as None (JSON has no NaN)."""
    return [None if not np.isfinite(v) else float(v) for v in np.ravel(values)]


def _array(values: list) -> np.ndarray:
    return np.array([np.nan if v is None else v for v in values], float)


@frozen(eq=False)
class FitQuality:
    """How well one image's radiometric correction fits, per band: the RMS
    of the corrected image minus the corrected images it was fitted to,
    over their co-located samples (data units), how many samples there
    were, and the bands left uncorrected because there were too few."""

    rms: np.ndarray  # (bands,), NaN where no samples
    samples: np.ndarray  # (bands,)
    defaulted: tuple[int, ...] = ()  # 0-based bands kept at gain 1, offset 0

    def state(self) -> dict:
        return {
            "rms": _jsonList(self.rms),
            "samples": [int(n) for n in self.samples],
            "defaulted": list(self.defaulted),
        }

    @classmethod
    def fromState(cls, state: dict) -> FitQuality:
        return cls(
            _array(state["rms"]),
            np.asarray(state["samples"], int),
            tuple(int(b) for b in state.get("defaulted", [])),
        )


@frozen(eq=False)
class OverlapAgreement:
    """Two overlapping images' mean absolute difference per band over their
    co-located samples, before and after the corrections (data units)."""

    first: int  # input keys
    second: int
    before: np.ndarray  # (bands,)
    after: np.ndarray
    samples: np.ndarray  # (bands,)

    def state(self) -> dict:
        return {
            "images": [self.first, self.second],
            "before": _jsonList(self.before),
            "after": _jsonList(self.after),
            "samples": [int(n) for n in self.samples],
        }

    @classmethod
    def fromState(cls, state: dict) -> OverlapAgreement:
        first, second = state["images"]
        return cls(
            int(first),
            int(second),
            _array(state["before"]),
            _array(state["after"]),
            np.asarray(state["samples"], int),
        )


@frozen(eq=False)
class RadiometryQuality:
    """A radiometric balance's quality: each corrected image's fit, and
    every overlap's agreement before and after."""

    fits: dict[int, FitQuality]  # by input key
    overlaps: tuple[OverlapAgreement, ...]

    def state(self) -> dict:
        return {
            "units": "data units of the inputs",
            "fits": {str(k): fit.state() for k, fit in self.fits.items()},
            "overlaps": [overlap.state() for overlap in self.overlaps],
        }

    @classmethod
    def fromState(cls, state: dict) -> RadiometryQuality:
        return cls(
            {int(k): FitQuality.fromState(v) for k, v in state["fits"].items()},
            tuple(OverlapAgreement.fromState(o) for o in state["overlaps"]),
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


class BlendMethod(LabeledEnum):
    NONE = "None (hard seams; keeps spectra exact)"
    FEATHER = "Feather (visual)"
    MULTIBAND = "Multi-band (visual)"


DEFAULT_FEATHER_WIDTH = 20  # pixels of the finest input
DEFAULT_LEVELS = 4


@frozen
class Blend:
    """How images mix across their seams. Anything but NONE mixes spectra, so
    the mosaic is a visual product."""

    method: BlendMethod = BlendMethod.NONE
    width: int = DEFAULT_FEATHER_WIDTH  # feather: the ramp's width, finest-input pixels
    levels: int = DEFAULT_LEVELS  # multi-band: pyramid levels

    def state(self) -> dict:
        return {"method": self.method.name, "width": self.width, "levels": self.levels}

    @classmethod
    def fromState(cls, state: dict) -> Blend:
        return cls(
            BlendMethod[state.get("method", "NONE")],
            int(state.get("width", DEFAULT_FEATHER_WIDTH)),
            int(state.get("levels", DEFAULT_LEVELS)),
        )
