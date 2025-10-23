from typing import Type
import numpy as np
from PyQt6.QtCore import QObject

from varda.common.parameter import IntParameter, ParameterGroup


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

    def parameters(self):
        """
        Returns a ParameterGroup object containing parameters for this stretch algorithm.
        If an algorithm has no parameters, they do not need to reimplement this method.
        """
        return ParameterGroup([])

    def apply(self, image):
        raise NotImplementedError("Subclasses classes must implement this method.")

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


@registerStretchAlgorithm("Min-Max (Full Range)")
class MinMaxStretch(StretchAlgorithm):
    """Simple min-max stretch that uses the full range of values in the image."""

    def parameters(self):
        return ParameterGroup([])

    def apply(self, image):
        """Compute min/max values for the full range of data."""
        validateArrayShape(image)

        if image.shape[2] == 1:
            # Handle grayscale or invalid data
            minVal = np.nanmin(image)
            maxVal = np.nanmax(image)
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

        return (np.clip(image, minVals, maxVals) - minVals) / (maxVals - minVals)


@registerStretchAlgorithm("Linear Percentile")
class LinearPercentileStretch(StretchAlgorithm):

    def __init__(self):
        super().__init__()
        self.lowPercent = IntParameter("Low Percent", "%", 1, [0, 100], self)
        self.highPercent = IntParameter("High Percent", "%", 99, [0, 100], self)

    def parameters(self):
        return ParameterGroup([self.lowPercent, self.highPercent])

    @staticmethod
    def computePercentile(data, percentile):
        """Safely compute percentile for masked or regular arrays."""
        # TODO: I don't think we should be making this function worry about masked/non-masked arrays?
        #   Varda Should prob just fill masked arrays with np.nan upfront.
        if np.ma.is_masked(data):
            # Use compressed() to get only non-masked values
            valid_data = data.compressed()
            return np.percentile(valid_data, percentile) if len(valid_data) > 0 else 0.0
        return np.nanpercentile(data, percentile)

    def apply(self, image):
        """Compute min/max values based on percentiles."""
        lowPercent = self.lowPercent.get()
        highPercent = self.highPercent.get()

        validateArrayShape(image)

        # Create a copy if the array is not writeable, because np.nanpercentile fails otherwise
        if not image.flags.writeable:
            image = image.copy()

        if image.shape[2] == 1:
            # Handle grayscale
            minVal = np.nanpercentile(image, lowPercent)
            maxVal = self.computePercentile(image, highPercent)
            # clip and stretch
            return (np.clip(image, minVal, maxVal) - minVal) / (maxVal - minVal)

        # Compute percentiles for each channel
        minVals = np.array(
            [
                self.computePercentile(image[:, :, 0], lowPercent),
                self.computePercentile(image[:, :, 1], lowPercent),
                self.computePercentile(image[:, :, 2], lowPercent),
            ]
        ).reshape((1, 1, 3))
        maxVals = np.array(
            [
                self.computePercentile(image[:, :, 0], highPercent),
                self.computePercentile(image[:, :, 1], highPercent),
                self.computePercentile(image[:, :, 2], highPercent),
            ]
        ).reshape((1, 1, 3))

        # clip and stretch
        return (np.clip(image, minVals, maxVals) - minVals) / (maxVals - minVals)
