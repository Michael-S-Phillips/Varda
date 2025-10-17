from typing import Protocol

import numpy as np
from pyqtgraph.parametertree import Parameter
from varda.common.parameter import IntParameter


stretchAlgorithmRegistry = {}


def registerStretchAlgorithm(cls):
    def wrapper(*args, **kwargs):
        return cls(*args, **kwargs)

    stretchAlgorithmRegistry[cls.__name__] = wrapper
    return wrapper


class StretchAlgorithm(Protocol):

    def parameters(self):
        raise NotImplementedError("Subclasses classes must implement this method.")

    def apply(self, image):
        raise NotImplementedError("Subclasses classes must implement this method.")


@registerStretchAlgorithm
class MinMaxStretch(StretchAlgorithm):
    """Simple min-max stretch that uses the full range of values in the image."""

    def parameters(self):
        return {}

    def apply(self, image):
        """Compute min/max values for the full range of data."""
        if image.ndim != 3 or image.shape[2] not in (1, 3):
            raise ValueError("Image must be 3-dimensional greyscale or RGB.")

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


@registerStretchAlgorithm
class LinearPercentileStretch(StretchAlgorithm):
    def __init__(self):
        super().__init__()
        # self.lowPercent = Parameter.create("Low Percent", )
        self.lowPercent = IntParameter("Low Percent", "%", [0, 100], 1)
        self.highPercent = IntParameter("High Percent", "%", [0, 100], 1)

    def parameters(self):
        return [self.lowPercent, self.highPercent]

    def computePercentile(self, data, percentile):
        """Safely compute percentile for masked or regular arrays."""
        # TODO: I don't think we should be making this function worry about masked/non-masked arrays.
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

        if image.ndim != 3 or image.shape[2] not in (1, 3):
            raise ValueError("Image must be 3-dimensional greyscale or RGB.")
        if image.shape[2] == 1:
            # Handle grayscale
            np.nanpercentile(image, lowPercent)
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
