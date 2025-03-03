# standard library
import time
from typing import override

# third party imports

import h5py

# local imports
from features.image_load.abstractimageloader import AbstractImageLoader
from core.entities.metadata import Metadata

from core.utilities import debug


class HDF5ImageLoader(AbstractImageLoader):  # pylint: disable=too-few-public-methods
    """Implementation of AbstractImageLoader for HDF5 Images"""

    imageType = ".h5"

    @staticmethod
    @override
    def _loadRasterData(filePath):

        timeStarted = time.time()

        with h5py.File(filePath, "r") as hdf:
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
            data = dataset[:]
            print(type(data))
            print("time to read data: ", time.time() - timeStarted)

        return data

    @staticmethod
    @override
    def _loadMetadata(image, filePath):
        with h5py.File(filePath, "r") as hdf:
            metadata = hdf["SERC/Reflectance/Metadata"]
            spectralData = metadata["Spectral_Data"]

            if image is not None:
                dtype = type(image)
                width = image.shape[0]
                height = image.shape[1]
                bandCount = image.shape[2]
            else:
                dtype = None
                width = None
                height = None
                bandCount = None
            wavelength = spectralData["Wavelength"][:]

        return Metadata(
            _filename=filePath,
            _driver="HDF5",
            _width=width,
            _height=height,
            _dtype=dtype,
            _bandCount=bandCount,
            _wavelength=wavelength,
        )
