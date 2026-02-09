from typing import Type
import numpy as np
from numba import njit, prange

from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QWidget

from varda.common.parameter import IntParameter, ParameterGroup
from varda.utilities.debug import Profiler

# TODO: Implement the other stretch algorithms:
# - Gaussian Stretch
# - Logarithmic Stretch
# - Square Root Stretch
# - Decorrelation Stretch
# - Histogram Equalization Stretch
# - Adaptive Equalization Stretch


def registerStretchAlgorithm(name):
    def wrapper(cls):
        cls.name = name
        stretchAlgorithmRegistry[name] = cls
        return cls

    return wrapper


stretchAlgorithmRegistry: dict[str, Type["StretchAlgorithm"]] = {}


def validateArrayShape(image):
    if image.ndim != 3 or image.shape[2] not in (1, 3):
        raise ValueError(
            f"Image must be 3-dimensional greyscale or RGB. Got {image.shape} "
        )


class StretchAlgorithm(QObject):
    def parameters(self) -> ParameterGroup:
        """
        Returns a ParameterGroup object containing parameters for this stretch algorithm.
        If an algorithm has no parameters, they do not need to reimplement this method.
        """
        return ParameterGroup()

    def apply(self, image: np.ndarray) -> np.ndarray:
        raise NotImplementedError("Subclasses classes must implement this method.")

    def minMaxVals(self) -> tuple[np.ndarray, np.ndarray] | None:
        return None

    def __repr__(self):
        params = self.parameters()
        out = f"{self.__class__.__name__} ( {params} )"
        return out


@registerStretchAlgorithm("No Stretch")
class NoStretch(StretchAlgorithm):
    """
    placeholder stretch algorithm that does nothing.
    """

    def apply(self, image):
        return image

    def minMaxVals(self):
        return None


@njit
def normalize(image, minVals, maxVals):
    scale = maxVals - minVals + 1e-10  # prevent division by zero
    return (np.clip(image, minVals, maxVals) - minVals) / scale


@njit(parallel=True)
def normalize_numba(image, minVals, maxVals):
    if len(minVals) != image.shape[2] or len(maxVals) != image.shape[2]:
        raise ValueError(
            "minVals and maxVals must have the same number of channels as the image"
        )

    out = np.empty_like(image)
    h, w, c = image.shape

    for i in prange(h):
        for j in range(w):
            for k in range(c):
                v = image[i, j, k]
                lo = minVals[k]
                hi = maxVals[k]

                if v < lo:
                    v = lo
                elif v > hi:
                    v = hi

                out[i, j, k] = (v - lo) / (hi - lo + 1e-10)
    return out


@registerStretchAlgorithm("Min-Max (Full Range)")
class MinMaxStretch(StretchAlgorithm):
    """Simple min-max stretch that uses the full range of values in the image."""

    def __init__(self):
        super().__init__()
        self.minVals = None
        self.maxVals = None

    def apply(self, image):
        """Compute min/max values for the full range of data."""
        validateArrayShape(image)

        if image.shape[2] == 1:
            # Handle grayscale or invalid data
            minVal = np.nanmin(image)
            maxVal = np.nanmax(image)
            self.minVals = minVal
            self.maxVals = maxVal
            return (np.clip(image, minVal, maxVal) - minVal) / (maxVal - minVal)

        # Compute percentiles for each channel
        minVals = np.array(
            [
                np.nanmin(image[:, :, 0]),
                np.nanmin(image[:, :, 1]),
                np.nanmin(image[:, :, 2]),
            ]
        ).reshape((1, 1, 3))
        maxVals = np.array(
            [
                np.nanmax(image[:, :, 0]),
                np.nanmax(image[:, :, 1]),
                np.nanmax(image[:, :, 2]),
            ]
        ).reshape((1, 1, 3))

        self.minVals = minVals.squeeze()
        self.maxVals = maxVals.squeeze()

        return (np.clip(image, minVals, maxVals) - minVals) / (maxVals - minVals)

    def minMaxVals(self):
        if self.minVals is not None and self.maxVals is not None:
            return self.minVals, self.maxVals
        else:
            return None


@njit(parallel=True)
def rgb_histogram(vals, hist, vmin, vmax):
    n, c = vals.shape
    nbins = hist.shape[1]
    scale = nbins / (vmax - vmin)

    for ch in prange(c):
        h = hist[ch]
        for i in range(n):
            v = vals[i, ch]
            if v == v:  # NaN check
                b = int((v - vmin) * scale)
                if b < 0:
                    b = 0
                elif b >= nbins:
                    b = nbins - 1
                h[b] += 1


def percentile_from_hist(hist, edges, p):
    target = p / 100 * hist.sum()
    return edges[np.searchsorted(np.cumsum(hist), target)]


def rgb_hist_percentiles_numba(
    rgb,
    lowPercent,
    highPercent,
    bins=1024,
    vmin=None,
    vmax=None,
):
    """
    Alternate method for approximating percentiles using a histogram approach.
    It's much faster than np.nanpercentile, but also slightly less accurate.
    I dont know for certain if this is okay or not (I think the error is smaller than what can be seen on a display), but for now not using it.
    """
    flat = rgb.reshape(-1, 3)

    if vmin is None:
        vmin = np.nanmin(flat)
    if vmax is None:
        vmax = np.nanmax(flat)

    hist = np.zeros((3, bins), dtype=np.int64)
    rgb_histogram(flat, hist, vmin, vmax)

    edges = np.linspace(vmin, vmax, bins + 1)

    minVals = np.empty(3, dtype=rgb.dtype)
    maxVals = np.empty(3, dtype=rgb.dtype)

    for c in range(3):
        minVals[c] = percentile_from_hist(hist[c], edges, lowPercent)
        maxVals[c] = percentile_from_hist(hist[c], edges, highPercent)

    return minVals, maxVals


@registerStretchAlgorithm("Linear Percentile")
class LinearPercentileStretch(StretchAlgorithm):
    class Config(ParameterGroup):
        highPercent = IntParameter(
            "High Percent",
            99,
            (0, 100),
            "%",
            "upper percentile of data to cut off",
        )
        lowPercent = IntParameter(
            "Low Percent",
            1,
            (0, 100),
            "%",
            "lower percentile of data to cut off",
        )

    def __init__(self) -> None:
        super().__init__()
        self.config = self.Config()

        self.minVals: np.ndarray | None = None
        self.maxVals: np.ndarray | None = None

    def parameters(self) -> ParameterGroup:
        return self.config

    def apply(self, image: np.ndarray) -> np.ndarray:
        """Compute min/max values based on percentiles.

        NOTE: This is an approximation, since we are sampling 1/4th of the pixels for better performance.
            For visualization purposes that's probably fine, but maybe not for more specific analysis?
            We can remove the optimization if so, or make it configurable."""

        profile = Profiler()
        lowPercent = self.config.lowPercent.value
        highPercent = self.config.highPercent.value

        validateArrayShape(image)
        profile("LinearPercentileStretch: Validated array shape")
        # Create a copy if the array is not writeable, because np.nanpercentile fails otherwise
        if not image.flags.writeable:
            image = image.copy()
            profile("LinearPercentileStretch: Copied array")

        # sample = image[::2, ::2]  # 1/4th pixels
        sample = image
        profile("LinearPercentileStretch: Created sample")
        if image.shape[2] == 1:
            # Handle grayscale; format as arrays for consistency with RGB case
            minVal = np.asarray([np.nanpercentile(sample, lowPercent)])
            maxVal = np.asarray([np.nanpercentile(sample, highPercent)])
            # clip and stretch
            # scale = maxVal - minVal
            # scale = 1.0 if scale == 0 else scale  # prevent division by zero
            self.minVals = minVal
            self.maxVals = maxVal
            profile("LinearPercentileStretch: Computed percentiles for grayscale image")
            result = normalize_numba(image, minVal, maxVal)
            profile("LinearPercentileStretch: stretched grayscale image")
            profile.total("LinearPercentileStretch: Total time")
            return result
        else:
            flat = sample.reshape(-1, 3)
            minVals = np.empty(3)
            maxVals = np.empty(3)

            for c in range(3):
                vals = flat[:, c]
                vals = vals[~np.isnan(vals)]
                vals_len = len(vals)
                k_low = int(vals_len * lowPercent / 100)
                k_high = int(vals_len * highPercent / 100)
                minVals[c] = np.partition(vals, k_low)[k_low]
                maxVals[c] = np.partition(vals, k_high)[k_high]

            # Compute percentiles for each channel
            # minVals = np.nanpercentile(sample, lowPercent, axis=(0, 1))
            # maxVals = np.nanpercentile(sample, highPercent, axis=(0, 1))

            # clip and stretch
            # scale = maxVals - minVals
            # scale[scale == 0] = 1.0  # prevent division by zero

            self.minVals = minVals
            self.maxVals = maxVals
            profile("LinearPercentileStretch: Computed percentiles for RGB image")
            result = normalize_numba(image, minVals, maxVals)
            profile("LinearPercentileStretch: stretched RGB image")
            profile.total("LinearPercentileStretch: Total time")
            return result

    def minMaxVals(self) -> tuple[np.ndarray, np.ndarray] | None:
        if self.minVals is not None and self.maxVals is not None:
            return self.minVals, self.maxVals
        else:
            return None
