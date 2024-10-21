# standard library

# third-party imports
import numpy as np

# local imports
import vardaconfig


class Metadata():
    """
    A standardized set of metadata for images. driver, dtype, dataignore, width,
    height, bandcount, and transform, are expected to be provided by every image.
    **kwargs lets you add additional metadata properties
    """

    def __init__(self,
                 driver=None,
                 dtype=None,
                 dataignore=None,
                 width=None,
                 height=None,
                 bandcount=None,
                 transform=None,
                 **kwargs):
        self.driver = driver
        self.dtype = dtype
        self.dataignore = dataignore
        self.width = width
        self.height = height
        self.bandcount = bandcount
        self.transform = transform

        for key, value in kwargs.items():
            if not hasattr(self, key):
                setattr(self, key, value)

    # def __init__(self, **kwargs):
    #     for key, value in kwargs.items():
    #         if not hasattr(self, key):
    #             setattr(self, key, value)
    #     pass
    #
    # def __init__(self, image):
    #     super().__init__()
    #     if vardaconfig.DEBUG:
    #         print("Raw Metadata:", image.meta)
    #
    #     # get rasterio metadata
    #     self['width'] = image.width
    #     self['height'] = image.height
    #     self['bands'] = image.count
    #     self['pixel size'] = image.res
    #     self['crs'] = image.crs
    #     self['transform'] = image.transform
    #     try:
    #         self['dtype'] = image.dtypes[0]
    #     except IndexError:
    #         self['dtype'] = None
    #         print("no dtype")
    #
    #     self['no data value'] = image.nodata
    #     self['driver'] = image.driver
    #
    #     # get envi metadata
    #     envi_data = image.tags(ns="ENVI")
    #     if vardaconfig.DEBUG:
    #         print("Raw Metadata:", envi_data)
    #     self["description"] = envi_data["description"].strip(
    #         "{}") if "description" in envi_data else None
    #
    #     default_bands = envi_data[
    #         "default_bands"] if "default_bands" in envi_data else None
    #     if default_bands:
    #         default_bands = [int(band) for band in
    #                          envi_data["default_bands"].strip("{}").split(',')]
    #         default_bands = {'r': default_bands[0], 'g': default_bands[1],
    #                          'b': default_bands[2]}
    #     self["default bands"] = default_bands
    #
    #     self["wavelength units"] = envi_data[
    #         "wavelength_units"] if "wavelength_units" in envi_data else None
    #     self["band names"] = np.asarray(envi_data["band_names"].strip("{}").split(
    #         ',')) if "band_names" in envi_data else None
    #
    #     wavelength = envi_data["wavelength"] if "wavelength" in envi_data else None
    #     if wavelength is not None:
    #         wavelength = np.asarray(
    #             [float(wavelength) for wavelength in wavelength.strip("{}").split(',')])
    #     self["wavelength"] = wavelength
    #     self["geospatial info"] = envi_data[
    #         "geospatial_info"] if "geospatial_info" in envi_data else None
    #
    #     # print("ENVI RAW DATA")
    #     # for key, value in envi_data.items():
    #     #     print(f"    {key}: {value}")
    #
    #     self._image_bounds = None
    #     self._no_data_vals = None

    def __iter__(self):
        for attr, value in self.__dict__.items():
            yield attr, value

    def __repr__(self):
        out = "Metadata:\n"
        for key, value in self.items():
            out += "    " + f"{key}: {value}" + "\n"
        return out
