# standard library
import time
from typing import override

# third party imports
import numpy as np
import rasterio as rio

# local imports
from speclabimageprocessing.image import Image
from speclabimageprocessing.metadata import Metadata
import vardaconfig


class ENVIImage(Image):

    image_type = ".img"

    @override
    def __init__(self, file_path):
        print("ENVI subclass Used")

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
        with rio.open(self._file_path) as src:
            print("time to open file: ", time.time() - timeStarted)

            # TODO: we should probably mask the array manually. masked=True makes this
            #  return a MaskedArray which is much slower
            timeStarted = time.time()
            self._data = src.read(masked=True).transpose(1, 2, 0)
            print("time to read data: ", time.time() - timeStarted)

            self._meta = self._parse_metadata(src)
        # get default bands
        self.default_bands = self._meta.default_bands

    def _parse_metadata(self, image):

        # get rasterio metadata
        if vardaconfig.DEBUG:
            print(image.meta)
        driver = image.driver

        try:
            dtype = image.dtypes[0]
        except IndexError:
            dtype = None
            print("no dtype")

        dataignore = image.nodata
        width = image.width
        height = image.height
        bandcount = image.count
        resolution = image.res
        crs = image.crs
        transform = image.transform

        # get envi metadata
        envi_data = image.tags(ns="ENVI")
        if vardaconfig.DEBUG:
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

    @override
    def request_rgb_data(self, bands):
        redBand = bands['r']
        greenBand = bands['g']
        blueBand = bands['b']

    @property
    def data(self):
        return self._data.data

    @property
    def meta(self):
        return self._meta
