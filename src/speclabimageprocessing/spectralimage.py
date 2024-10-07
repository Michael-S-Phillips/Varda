from abc import abstractmethod
import spectral
import rasterio as rio
import numpy as np
from skimage import exposure
import re


class SpectralImage:
    # dictionary of all subclasses of SpectralImage, mapped to their associated keyword
    subclasses = {}

    # this forces subclasses to set this value
    @property
    @abstractmethod
    def image_type(self):
        pass

    """
    runs whenever a subclass is declared. adds it to the list of available subclasses
    """
    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.subclasses[cls.image_type] = cls

    """
    determines which subclass is needed and returns a new instance of it
    """
    @classmethod
    def new_image(cls, file_path):
        # TODO: possibly need more complex system to determine file type? right now its just based on the file extension
        image_type = re.search("hdr$", file_path).group()
        if image_type not in cls.subclasses:
            raise ValueError(f"Bad file type {image_type}")
        return cls.subclasses[image_type](file_path)

    def __init__(self, file_path):
        self.file_path = file_path
        self.data = None
        self.transform = None
        self.default_rgb_bands = (29, 19, 9)  # Example default bands
        self.image = self.load_data()

    """
    loads a spectral image
    """
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
        left_red_stretch = (0, 1)
        left_green_stretch = (0, 1)
        left_blue_stretch = (0, 1)

        # Extract the RGB bands
        rgb_image = self.data[:, :, [band_indices[0], band_indices[1], band_indices[2]]]

        rgb_image[:, :, 0] = self.stretch_band(rgb_image[:, :, 0], left_red_stretch)
        rgb_image[:, :, 1] = self.stretch_band(rgb_image[:, :, 1], left_green_stretch)
        rgb_image[:, :, 2] = self.stretch_band(rgb_image[:, :, 2], left_blue_stretch)

        # Normalize each band
        # for i in range(3):
        #     band = rgb_image[:, :, i]
        #     p2, p98 = np.percentile(band, (2, 98))
        #     rgb_image[:, :, i] = exposure.rescale_intensity(band, in_range=(p2, p98))
        #
        # # Apply CLAHE to enhance contrast
        # for i in range(3):
        #     rgb_image[:, :, i] = exposure.equalize_adapthist(rgb_image[:, :, i], clip_limit=0.03)

        print(f"RGB image shape: {rgb_image.shape}")
        print(f"RGB image dtype: {rgb_image.dtype}")
        print(f"RGB image min: {np.min(rgb_image)}, max: {np.max(rgb_image)}")

        return rgb_image

    def stretch_band(self, band, stretch_range):
        min_val, max_val = stretch_range
        stretched_band = (band - min_val) / (max_val - min_val)
        stretched_band = np.clip(stretched_band, 0, 1)
        return stretched_band