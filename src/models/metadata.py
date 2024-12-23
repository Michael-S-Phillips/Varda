# standard library
from typing import Any

# third-party imports
from PyQt6.QtCore import QAbstractListModel, QModelIndex, Qt
from affine import Affine
import numpy as np
from dataclasses import dataclass


# local imports

@dataclass
class MetaDataValue:
    name: str
    value: Any


class Metadata:
    """
    A standardized set of metadata for images. driver, dtype, dataignore, width,
    height, bandcount, and transform, are expected to be provided by every image.
    **kwargs lets you add additional metadata properties for displaying and editing.

    individual sections of metadata can be accessed using dot-notation.
    the entire metadata object can also be iterated through as if it were a dictionary
    """

    def __init__(self,
                 driver: str,
                 dtype: str,
                 dataignore: float,
                 width: int,
                 height: int,
                 bandcount: int,
                 default_bands: dict,
                 transform: Affine,
                 wavelength: np.ndarray,
                 **kwargs):
        super().__init__()

        if default_bands is None:
            default_bands = {}
        if transform is None:
            transform = Affine.identity()
        if wavelength is None:
            wavelength = np.array([])


        # set base args
        self.driver = driver
        self.dtype = dtype
        self.dataignore = dataignore
        self.width = width
        self.height = height
        self.bandcount = bandcount
        self.default_bands = default_bands

        self.transform = transform
        self.wavelength = wavelength

        # add additional args
        for key, value in kwargs.items():
            if not hasattr(self, key):
                setattr(self, key, value)
        self.numExtraArgs = len(kwargs)

    def save(self, out):
        """
        Save the metadata to a QDataStream
        """
        out.writeString(self.driver)
        out.writeString(self.dtype)
        out.writeFloat(self.dataignore)
        out.writeInt32(self.width)
        out.writeInt32(self.height)
        out.writeInt32(self.bandcount)
        out.writeFloat(self.transform.a)
        out.writeFloat(self.transform.b)
        out.writeFloat(self.transform.c)
        out.writeFloat(self.transform.d)
        out.writeFloat(self.transform.e)
        out.writeFloat(self.transform.f)

        out.writeInt32(len(self.wavelength))
        for w in self.wavelength:
            out.writeFloat(w)

        out.writeInt32(len(self.default_bands))
        for band in self.default_bands.values():
            out.writeInt32(band.r)
            out.writeInt32(band.g)
            out.writeInt32(band.b)

        out.writeInt32(self.numExtraArgs)
        for key, value in self:
            out.writeString(key)
            out.writeString(value)

    @classmethod
    def load(cls, inStream):
        """
        Load the metadata from a QDataStream
        """
        driver = inStream.readString()
        dtype = inStream.readString()
        dataignore = inStream.readFloat()
        width = inStream.readInt32()
        height = inStream.readInt32()
        bandcount = inStream.readInt32()
        a = inStream.readFloat()
        b = inStream.readFloat()
        c = inStream.readFloat()
        d = inStream.readFloat()
        e = inStream.readFloat()
        f = inStream.readFloat()
        transform = Affine(a, b, c, d, e, f)
        wavelength = np.array([inStream.readFloat() for _ in range(inStream.readInt32())])
        default_bands = {}
        for _ in range(inStream.readInt32()):
            r = inStream.readInt32()
            g = inStream.readInt32()
            b = inStream.readInt32()
            band = MetaDataValue("band", r, g, b)
            default_bands[band.name] = band
        kwargs = {}
        while not inStream.atEnd():
            key = inStream.readString()
            value = inStream.readString()
            kwargs[key] = value
        return cls(driver, dtype, dataignore, width, height, bandcount,
                   default_bands, transform, wavelength)

    def __iter__(self):
        for attr, value in self.__dict__.items():
            yield attr, value

    def __repr__(self):
        out = "Metadata:\n"
        for key, value in self:
            out += "    " + f"{key}: {value}" + "\n"
        return out
