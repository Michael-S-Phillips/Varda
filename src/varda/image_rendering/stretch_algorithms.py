from typing import Type
import numpy as np
from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QWidget
from varda.common.parameter import IntParameter, ParameterGroup


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
        lowPercent = self.config.lowPercent.value
        highPercent = self.config.highPercent.value

        validateArrayShape(image)

        # Create a copy if the array is not writeable, because np.nanpercentile fails otherwise
        if not image.flags.writeable:
            image = image.copy()

        sample = image[::2, ::2]  # 1/4th pixels
        if image.shape[2] == 1:
            # Handle grayscale
            minVal = np.nanpercentile(sample, lowPercent)
            maxVal = np.nanpercentile(sample, highPercent)
            # clip and stretch
            scale = maxVal - minVal
            scale = 1.0 if scale == 0 else scale  # prevent division by zero
            self.minVals = minVal
            self.maxVals = maxVal
            return (np.clip(image, minVal, maxVal) - minVal) / scale
        else:
            # Compute percentiles for each channel
            minVals = np.nanpercentile(sample, lowPercent, axis=(0, 1), keepdims=True)
            maxVals = np.nanpercentile(sample, highPercent, axis=(0, 1), keepdims=True)
            # clip and stretch
            scale = maxVals - minVals
            scale[scale == 0] = 1.0  # prevent division by zero

            self.minVals = np.squeeze(minVals)
            self.maxVals = np.squeeze(maxVals)

            return (np.clip(image, minVals, maxVals) - minVals) / scale

    def minMaxVals(self) -> tuple[np.ndarray, np.ndarray] | None:
        if self.minVals is not None and self.maxVals is not None:
            return self.minVals, self.maxVals
        else:
            return None
