class ImageContext:

    raster: np.ndarray
    metadata: Metadata
    stretch: Stretch
    band: Band

    def height(self):
        return self.raster.shape[0]

    def width(self):
        return self.raster.shape[1]
