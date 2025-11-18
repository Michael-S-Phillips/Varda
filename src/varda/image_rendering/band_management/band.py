class BandConfiguration:
    """Band Configuration"""

    def __init__(self, mode, values, colorMap=None):
        self.mode = mode
        self.values = values
        self.colorMap = colorMap

    def apply(self, image):
        """Apply the band configuration to the image"""
        if self.mode == "rgb":
            return image[:, :, self.values]
        elif self.mode == "mono":
            data = image[:, :, self.values[0]]
            return self.colorMap(data)
