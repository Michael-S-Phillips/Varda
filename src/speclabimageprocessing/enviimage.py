# standard library
import time
from typing import override

# third party imports
import numpy as np
import rasterio as rio

# local imports
from speclabimageprocessing.image import Image
from speclabimageprocessing.metadata import Metadata


class ENVIImage(Image):

    @property
    def data(self):
        return self._data.data

    @property
    def meta(self):
        return self._meta

    image_type = ".img"

    @override
    def __init__(self, file_path):
        print("ENVI subclass Used")

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

        # self._file = rio.open(self._file_path)
        timeStarted = time.time()
        with rio.open(self._file_path) as src:
            print("time to open file: ", time.time() - timeStarted)

            # TODO: we should probably mask the array manually. masked=True makes this
            #  return a MaskedArray which is much slower
            timeStarted = time.time()
            self._data = src.read(masked=True).transpose(1, 2, 0)
            print("time to read data: ", time.time() - timeStarted)

            self._meta = Metadata(src)

        # get default bands
        self.default_bands = self._meta["default bands"]

    def calculate_mean(self):
        pass

    def request_rgb_data(self, bands):
        redBand = bands['r']
        greenBand = bands['g']
        blueBand = bands['b']
