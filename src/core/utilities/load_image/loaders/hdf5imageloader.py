# standard library
import time
from typing import override

# third party imports
import h5py
import numpy as np

# local imports
from core.utilities.load_image.loaders.abstractimageloader import AbstractImageLoader
from core.entities.metadata import Metadata

from core.utilities import debug


class HDF5ImageLoader(AbstractImageLoader):  # pylint: disable=too-few-public-methods
    """Implementation of AbstractImageLoader for HDF5 Images"""

    imageType = ".h5"

    @staticmethod
    def loadRasterData(filePath) -> np.ndarray:

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
    def loadMetadata(raster, filePath) -> Metadata:
        with h5py.File(filePath, "r") as hdf:
            metadata = hdf["SERC/Reflectance/Metadata"]
            spectralData = metadata["Spectral_Data"]

            if raster is not None:
                dtype = type(raster)
                width = raster.shape[0]
                height = raster.shape[1]
                bandCount = raster.shape[2]
            else:
                dtype = None
                width = None
                height = None
                bandCount = None
            wavelengths = spectralData["Wavelength"][:]

        return Metadata(
            filePath=filePath,
            driver="HDF5",
            width=width,
            height=height,
            dtype=dtype,
            bandCount=bandCount,
            wavelengths=wavelengths,
        )
