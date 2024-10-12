from abc import abstractmethod
from types import MappingProxyType
from typing import override, final

import spectral
import rasterio as rio
import numpy as np
from skimage import exposure
import re
import json


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

    @override
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
        self._file_path = file_path

        self._file = None
        self._meta = None
        self._header_data = None
        self._data = None
        self._data_transposed = None
        self.transform = None
        self.default_bands = {'r': 29, 'g': 19, 'b': 9}  # Example default bands
        self.image = self.load_data()
        # dict mapping value types to indexes (t is the spectral data)
        self.axes = {'x': 0, 'y': 1, 't': 2}

    """
    public getter for img data, which returns the array in the format [width, height, channel] for plotting
    """

    @property
    def data(self):
        return self._data.T

    """
    returns the range of image (lowest and highest value). 
    For now just returning 0 and 1 because every image should be normalized
    """

    @property
    def range(self):
        return 0, 1

    @property
    def meta(self):
        return self._meta

    """
    loads a spectral image
    """

    def load_data(self):
        if self._file_path is None:
            return

        # Load geospatial data
        rio_path = self._file_path.replace("hdr", "img")
        self._file = rio.open(rio_path)
        self._data = self._file.read(masked=True)
        self._meta = Metadata(self._file)

        # get default bands
        self.default_bands = self._meta["default bands"]
        print("default bands: ", self.default_bands)

        self.transform = self._file.transform
        print(self._file.width, self._file.height)
        print(self._file.crs)
        print(self._file.transform)
        print(self._file.count)
        print(self._file.indexes)

        self.calculate_mean()
        return self.display_data()

    def display_data(self):
        if self._data is not None:
            return self.display_rgb_data(self.default_bands)

    def display_rgb_data(self, band_indices):
        left_red_stretch = (0, 1)
        left_green_stretch = (0, 1)
        left_blue_stretch = (0, 1)

        # Extract the RGB bands
        rgb_image = self._data[[band_indices['r'], band_indices['g'], band_indices['b']], :, :]

        rgb_image[0, :, :] = self.stretch_band(rgb_image[0, :, :], left_red_stretch)
        rgb_image[1, :, :] = self.stretch_band(rgb_image[1, :, :], left_green_stretch)
        rgb_image[2, :, :] = self.stretch_band(rgb_image[2, :, :], left_blue_stretch)

        # # Normalize each band
        # for i in range(3):
        #     band = rgb_image[:, :, i]
        #     p2, p98 = np.percentile(band, (2, 98))
        #     rgb_image[:, :, i] = exposure.rescale_intensity(band, in_range=(p2, p98))
        #
        # # Apply CLAHE to enhance contrast
        # for i in range(3):
        #     rgb_image[:, :, i] = exposure.equalize_adapthist(rgb_image[:, :, i], clip_limit=0.03)

        return rgb_image

    """
    requests a subset of the image data, based on the given band parameters to use for rgb indexes
    """

    def request_rgb_data(self, bands):
        pass

    def stretch_band(self, band, stretch_range):
        min_val, max_val = stretch_range
        stretched_band = (band - min_val) / (max_val - min_val)
        stretched_band = np.clip(stretched_band, 0, 1)
        return stretched_band

    def calculate_mean(self):
        return np.mean(self._data, axis=(1, 2))


class Metadata(dict):
    def __init__(self, image):
        super().__init__()

        # get rasterio metadata
        self['width'] = image.width
        self['height'] = image.height
        self['bands'] = image.count
        self['pixel size'] = image.res
        self['crs'] = image.crs
        self['dtype'] = image.dtypes[0]
        self['no data value'] = image.nodata
        self['driver'] = image.driver

        # get envi metadata
        envi_data = image.tags(ns="ENVI")
        self["description"] = envi_data["description"].strip("{}") if "description" in envi_data else None

        default_bands = envi_data["default_bands"] if "default_bands" in envi_data else None
        if default_bands:
            default_bands = [int(band) for band in envi_data["default_bands"].strip("{}").split(',')]
            default_bands = {'r': default_bands[0], 'g': default_bands[1], 'b': default_bands[2]}
        self["default bands"] = default_bands

        self["wavelength units"] = envi_data["wavelength_units"] if "wavelength_units" in envi_data else None
        self["band names"] = envi_data["band_names"].strip("{}").split(',') if "band_names" in envi_data else None

        wavelength = envi_data["wavelength"] if "wavelength" in envi_data else None
        self["wavelength"] = [float(wavelength) for wavelength in wavelength.strip("{}").split(',')]

        self["geospatial info"] = envi_data["geospatial_info"] if "geospatial_info" in envi_data else None

        print("ENVI RAW DATA")
        for key, value in envi_data.items():
            print(f"    {key}: {value}")

        print(self)
        self._image_bounds = None
        self._no_data_vals = None

    def __repr__(self):
        out = "Metadata:\n"
        for key, value in self.items():
            out += "    " + f"{key}: {value}" + "\n"
        return out
