import numpy as np


class ImageLayer:
    def __init__(self):
        self.image = None
        self.mode = "rgb"
        self.band = None
        self.stretch = None

    def render(self):
        """
        Render the image with the current band and stretch settings.
        Returns: numpy ndarray with shape (height, width, 3) representing an RGB image.

        """
        if self.image is None or self.band is None or self.stretch is None:
            raise ValueError("Image, band, and stretch must be set before rendering.")

        # Extract the raster data for the specified band
        rgb_image = self.band.apply(self.image.raster)

        # Apply the stretch to the raster data
        rgb_image = self.stretch.apply(rgb_image)

        return rgb_image
