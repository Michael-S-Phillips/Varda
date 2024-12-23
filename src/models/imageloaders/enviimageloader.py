# standard library
import time
import logging

# third party imports
import numpy as np
import rasterio as rio
logging.getLogger('rasterio').setLevel(logging.CRITICAL)

# local imports
from models.imageloaders.abstractimageloader import AbstractImageLoader
from models.metadata import Metadata
import debug


class ENVIImageLoader(AbstractImageLoader):

    imageType = (".hdr", ".img")

    @staticmethod
    def _loadRasterData(filePath=None):
        if filePath is None:
            return
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
    def _loadMetadata(image=None, filePath=None):
        if filePath is None:
            return

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

            dataignore = src.nodata
            width = src.width
            height = src.height
            bandcount = src.count
            resolution = src.res
            crs = src.crs
            transform = src.transform

            # get envi metadata
            envi_data = src.tags(ns="ENVI")
            if debug.DEBUG:
                print("Raw Metadata:", envi_data)

            description = envi_data["description"].strip(
                "{}") if "description" in envi_data else None

            default_bands = envi_data[
                "default_bands"] if "default_bands" in envi_data else None
            if default_bands:
                default_bands = [int(band) for band in
                                 envi_data["default_bands"].strip("{}").split(',')]
                default_bands = {'r': default_bands[0], 'g': default_bands[1],
                                 'b': default_bands[2]}

            wavelength_units = envi_data[
                "wavelength_units"] if "wavelength_units" in envi_data else None
            band_names = np.asarray(envi_data["band_names"].strip("{}").split(
                ',')) if "band_names" in envi_data else None

            wavelength = envi_data["wavelength"] if "wavelength" in envi_data else None
            if wavelength is not None:
                wavelength = np.asarray(
                    [float(wavelength) for wavelength in wavelength.strip("{}").split(',')])

            geospatial_info = envi_data[
                "geospatial_info"] if "geospatial_info" in envi_data else None

        return Metadata(driver=driver,
                        dtype=dtype,
                        dataignore=dataignore,
                        width=width,
                        height=height,
                        bandcount=bandcount,
                        default_bands=default_bands,
                        transform=transform,
                        wavelength=wavelength,
                        description=description,
                        wavelength_units=wavelength_units,
                        band_names=band_names,
                        geospatial_info=geospatial_info
                        )
