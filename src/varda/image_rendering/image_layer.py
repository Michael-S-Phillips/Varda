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
        rgb_data = self.band.apply(self.image)

        # TODO: handle nans/nodata values

        # Apply the stretch to the raster data
        rgb_data = self.stretch.apply(rgb_data)

        # TODO: handle color mapping

        return rgb_data
