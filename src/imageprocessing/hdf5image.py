# standard library
import time
from typing import override

# third party imports
import numpy as np
import rasterio as rio
import h5py

# local imports
from imageprocessing.image import Image
from imageprocessing.metadata import Metadata
import debug


class HDF5Image(Image):

    @property
    def data(self):
        return self._data

    @property
    def meta(self):
        return self._meta

    image_type = ".h5"

    @override
    def __init__(self, file_path):
        print("NEON subclass Used")

        self._file_path = file_path
        self._meta = None
        self._header_data = None
        self._data = None
        self.default_bands = {'r': 29, 'g': 19, 'b': 9}  # Example default bands
        self._load_data()
        self.mean = np.mean(self._data, axis=(0, 1))
        # dict mapping value types to indexes (t is the spectral data)
        self.axes = {'x': 0, 'y': 1, 't': 2}

    @override
    def _load_data(self):
        if self._file_path is None:
            return

        timeStarted = time.time()
        with h5py.File(self._file_path, 'r') as hdf:
            if debug.DEBUG:
                print("time to open file: ", time.time() - timeStarted)

            print("Available groups/datasets in the file:")
            hdf.visititems(lambda name, obj: print(f"{name}: {obj}"))

            # TODO: extract dataset without hardcoding
            f = hdf
            while len(f.keys()) == 1:
                keys = list(f.keys())
                f = f[keys[0]]


            dataset = hdf["SERC/Reflectance/Reflectance_Data"]
            timeStarted = time.time()
            self._data = dataset[:]
            print(type(self._data))
            print("time to read data: ", time.time() - timeStarted)
            metadata = hdf["SERC/Reflectance/Metadata"]
            self._meta = self._parse_metadata(self._data, metadata)

    def _parse_metadata(self, image, metadata):
        spectral_data = metadata["Spectral_Data"]

        dtype = type(image)
        width = image.shape[0]
        height = image.shape[1]
        bandcount = image.shape[2]

        wavelength = spectral_data["Wavelength"][:]

        return Metadata(driver=None,
                        dtype=dtype,
                        dataignore=None,
                        width=width,
                        height=height,
                        bandcount=bandcount,
                        default_bands=None,
                        transform=None,
                        wavelength=wavelength,
                        description=None,
                        wavelength_units=None,
                        band_names=None,
                        geospatial_info=None
                        )

    def request_rgb_data(self, bands):
        redBand = bands['r']
        greenBand = bands['g']
        blueBand = bands['b']
