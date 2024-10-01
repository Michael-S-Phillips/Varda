import spectral
import rasterio as rio
import numpy as np
from skimage import exposure

class SpectralDataViewer:
    def __init__(self, file_path):
        self.file_path = file_path
        self.data = None
        self.transform = None
        self.default_rgb_bands = (29, 19, 9)  # Example default bands
        self.image = self.load_data()

    def load_data(self):
        if self.file_path:
            # Load spectral data
            self.data = spectral.open_image(self.file_path)
            self.data = self.data.load()

            # Load geospatial data
            rio_path = self.file_path.replace("hdr", "img")
            with rio.open(rio_path) as dataset:
                self.transform = dataset.transform

            return self.display_data()

    def display_data(self):
        if self.data is not None:
            return self.display_rgb_data(self.default_rgb_bands)

    def display_rgb_data(self, band_indices):
        # Extract the RGB bands
        rgb_image = self.data[:, :, [band_indices[0], band_indices[1], band_indices[2]]]

        # Normalize each band
        for i in range(3):
            band = rgb_image[:, :, i]
            p2, p98 = np.percentile(band, (2, 98))
            rgb_image[:, :, i] = exposure.rescale_intensity(band, in_range=(p2, p98))

        # Apply CLAHE to enhance contrast
        for i in range(3):
            rgb_image[:, :, i] = exposure.equalize_adapthist(rgb_image[:, :, i], clip_limit=0.03)

        print(f"RGB image shape: {rgb_image.shape}")
        print(f"RGB image dtype: {rgb_image.dtype}")
        print(f"RGB image min: {np.min(rgb_image)}, max: {np.max(rgb_image)}")

        return rgb_image