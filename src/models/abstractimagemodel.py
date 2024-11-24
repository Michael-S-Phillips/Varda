
# standard library
from abc import ABCMeta, abstractmethod

# third party imports
from PyQt6 import QtCore
import pyqtgraph as pg
import numpy as np
import cv2

# local imports
from gui.customitems import TripleImageHistogram


class MetaClassThing(ABCMeta, type(QtCore.QObject)):
    pass


class AbstractImageModel(QtCore.QObject, metaclass=MetaClassThing):
    """
    Abstract base class for all images in varda.
    Allows for a consistent interface with the images.
    Getters/Methods that all image subclasses must provide:
        data -  ndarray containing the raw image data
        meta -  Metadata dictionary
    """
    roiChanged = QtCore.pyqtSignal()  # Signal when ROI changes
    bandChanged = QtCore.pyqtSignal()  # Signal when band adjustments change
    stretchChanged = QtCore.pyqtSignal()  # Signal when the stretch changes
    imageChanged = QtCore.pyqtSignal()  # Signal when anything about the image changes

    # dictionary of all subclasses of Image, mapped to their associated keyword
    subclasses = []

    def __init_subclass__(cls, **kwargs):
        """
        runs whenever a subclass is declared. adds it to the list of available subclasses
        """
        super().__init_subclass__(**kwargs)
        AbstractImageModel.subclasses.append(cls)

    def __init__(self):
        super().__init__()
        self.histogram = pg.HistogramLUTItem()

    @QtCore.pyqtSlot()
    @abstractmethod
    def process(self, process):
        """
        Executes a process on the image
        """
        pass

    @classmethod
    def __str__(cls):
        return "name: " + cls.__name__

    @classmethod
    def __repr__(cls):
        return "name: " + cls.__name__

    @property
    def imageSlice(self, bands=None):
        try:
            return self.data[:, :, list(self.bands.values())]
        except TypeError:
            raise TypeError("bands must be an iterable object (list, tuple, ndarray)")

    # @bands.setter()
    # def setBands(self, bands):
    #     self.bands = bands
    #     self.imageChanged.emit()
    #
    # def setStretch(self, stretch):
    #     self.stretch = stretch
    #     self.stretchChanged.emit()

    def imageItem(self):
        return pg.ImageItem(self.imageSlice(), levels=(0, 1))

    # "@property @abstractmethod" forces subclasses to declare the variable
    @property
    @abstractmethod
    def data(self):
        pass

    @property
    @abstractmethod
    def meta(self):
        pass

    @property
    @abstractmethod
    def bands(self):
        pass

    @property
    @abstractmethod
    def stretch(self):
        pass

    @property
    @abstractmethod
    def imageType(self):
        pass

    @property
    @abstractmethod
    def uint8_data(self):
        pass
