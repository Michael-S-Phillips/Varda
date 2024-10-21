# standard library
import time
from typing import override

# third party imports
import numpy as np
import rasterio as rio
import h5py

# local imports
from speclabimageprocessing.image import Image
from speclabimageprocessing.metadata import Metadata


class NEONImage(Image):

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
        self.load_data()
        self.mean = np.mean(self._data, axis=(0, 1))
        # dict mapping value types to indexes (t is the spectral data)
        self.axes = {'x': 0, 'y': 1, 't': 2}

    def load_data(self):
        if self._file_path is None:
            return

        timeStarted = time.time()
        with h5py.File(self._file_path, 'r') as hdf:
            print("time to open file: ", time.time() - timeStarted)

            print("Available groups/datasets in the file:")

            hdf.visititems(lambda name, obj: print(f"{name}: {obj}"))
            # TODO: extract dataset without hardcoding
            dataset = hdf["SERC/Reflectance/Reflectance_Data"]
            timeStarted = time.time()
            self._data = dataset[:]
            print("time to read data: ", time.time() - timeStarted)
        with rio.open(self._file_path) as src:
            self._meta = Metadata(src)

        # get default bands
        if self._meta["default bands"] is not None:
            self.default_bands = self._meta["default bands"]

    def request_rgb_data(self, bands):
        redBand = bands['r']
        greenBand = bands['g']
        blueBand = bands['b']
