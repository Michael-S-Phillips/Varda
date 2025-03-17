# standard library
import time
import logging

# third party imports
import numpy as np
import rasterio as rio

# local imports
from core.utilities.load_image.loaders.abstractimageloader import AbstractImageLoader
from core.entities.metadata import Metadata
from core.utilities import debug
from core.entities import Band

logging.getLogger("rasterio").setLevel(logging.CRITICAL)


class ENVIImageLoader(AbstractImageLoader):  # pylint: disable=too-few-public-methods
    """Implementation of AbstractImageLoader for ENVI Images"""

    imageType = (".hdr", ".img")

    @staticmethod
    def loadRasterData(filePath) -> np.ndarray:
        path = filePath.replace(".hdr", ".img")
        timeStarted = time.time()

        with rio.open(path) as src:
            print("time to open file: ", time.time() - timeStarted)

            # TODO: we should probably mask the array manually. masked=True makes this
            #  return a MaskedArray which is much slower
            timeStarted = time.time()
            data = src.read(masked=True).transpose(1, 2, 0)
            print("time to read data: ", time.time() - timeStarted)

        # get default bands
        return data

    @staticmethod
    def loadMetadata(raster, filePath) -> Metadata:  # pylint: disable=too-many-locals
        path = filePath.replace(".hdr", ".img")
        with rio.open(path) as src:
            # get rasterio metadata

            if debug.DEBUG:
                print(src.meta)
            driver = src.driver

            try:
                dtype = src.dtypes[0]
            except IndexError:
                dtype = None
                print("no dtype")

            dataIgnore = src.nodata
            width = src.width
            height = src.height
            bandCount = src.count
            resolution = src.res
            crs = src.crs
            transform = src.transform

            # get envi metadata
            enviData = src.tags(ns="ENVI")
            if debug.DEBUG:
                # print("Raw Metadata:", enviData)
                pass

            description = (
                enviData["description"].strip("{}")
                if "description" in enviData
                else None
            )

            defaultBands = (
                enviData["default_bands"] if "default_bands" in enviData else None
            )
            if defaultBands:
                defaultBands = [
                    int(band)
                    for band in enviData["default_bands"].strip("{}").split(",")
                ]
                defaultBands = Band("default", defaultBands[0], defaultBands[1], defaultBands[2])

            wavelengthUnits = (
                enviData["wavelength_units"] if "wavelength_units" in enviData else None
            )
            bandNames = (
                enviData["band_names"].strip("{}").split(",")
                if "band_names" in enviData
                else None
            )

            wavelengths = enviData["wavelength"] if "wavelength" in enviData else None
            if wavelengths is not None:
                wavelengths = np.asarray(
                    [
                        float(wavelength)
                        for wavelength in wavelengths.strip("{}").split(",")
                    ]
                )

            geospatialInfo = (
                enviData["geospatial_info"] if "geospatial_info" in enviData else None
            )

        return Metadata(
            filePath=filePath,
            driver=driver,
            width=width,
            height=height,
            dtype=dtype,
            dataIgnore=dataIgnore,
            bandCount=bandCount,
            defaultBand=defaultBands,
            wavelengths=wavelengths,
            extraMetadata={
                # "transform": transform,
                "description": description,
                "wavelength_units": wavelengthUnits,
                "band_names": bandNames,
                # "geospatial_info": geospatialInfo,
            },
        )
