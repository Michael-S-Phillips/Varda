# standard library
from abc import ABCMeta, abstractmethod
from enum import Enum, auto

# third party imports
from PyQt6 import QtCore
from PyQt6.QtCore import QAbstractItemModel, QModelIndex, pyqtSignal, Qt
import pyqtgraph as pg
import numpy as np
import cv2
# local imports
from gui.customitems import TripleImageHistogram


class VardaImageData(Enum):
    """
    Enum for the different types of image data
    """
    OBJECT = Qt.ItemDataRole.UserRole
    RASTER_DATA = auto()
    METADATA = auto()
    BANDS = auto()
    STRETCH = auto()
    HISTOGRAM = auto()


class TESTAbstractImageModelMeta(ABCMeta, type(QAbstractItemModel)):
    """
    Metaclass for AbstractImageModel. This needs to exist because QObject and ABC
    use different metaclasses.
    So this makes a metaclass that works for both. Or something like that.
    What is a metaclass? It's a class for classes. It defines how a class behaves.
    Why is that a thing? Because Python is weird.
    """
    pass


class TESTAbstractImageModel(QAbstractItemModel,
                             metaclass=TESTAbstractImageModelMeta):
    """
    Abstract base class for all images in varda.
    Allows for a consistent interface with the images.
    Getters/Methods that all image subclasses must provide:
        data -  ndarray containing the raw image data
        meta -  Metadata dictionary
    """
    roiChanged = pyqtSignal()  # Signal when ROI changes
    bandChanged = pyqtSignal()  # Signal when band adjustments change
    stretchChanged = pyqtSignal()  # Signal when the stretch changes
    imageChanged = pyqtSignal()  # Signal when anything about the image changes

    # dictionary of all subclasses of Image, mapped to their associated keyword
    subclasses = []

    def __init_subclass__(cls, **kwargs):
        """
        runs whenever a subclass is declared. adds it to the list of available subclasses
        """
        super().__init_subclass__(**kwargs)
        AbstractImageModel.subclasses.append(cls)

    def __init__(self, imageLoader=None):
        super().__init__()

        bands = {"mono": {'r': 0, 'g': 0, 'b': 0},
                       "rgb": {'r': 0, 'g': 1, 'b': 2},
                       "custom1": {'r': 10, 'g': 20, 'b': 30}
                       }
        stretch = {"0-1": (0, 1),
                         "0-255": (0, 255),
                         "custom1": (0, 1),
                         }
        roi = {}

        histogram = pg.HistogramLUTItem()
        self._dataParams = {"Image": self.data,
                            "Metadata": self.meta,
                            "Bands": bands,
                            "Stretch": stretch,
                            "ROI": roi,
                            "Histogram": histogram
                            }

    def rowCount(self, parent=QModelIndex()):
        # Top-level categories (Bands, Stretch, etc.)
        if not parent.isValid():
            return len(self._dataParams)

        # Child rows (keys in the selected category)
        category_data = parent.internalPointer()
        if isinstance(category_data, dict):
            return len(category_data)
        return 0

    def columnCount(self, parent=QModelIndex()):
        # Two columns: Key and Value
        return 2

    def createIndex(self, row, column, parent=None):
        return self.index(row, column, parent)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        # Top-level category names
        if not index.parent().isValid():
            if role == VardaImageData.RASTER_DATA:
                return self._dataParams["Image"]
            if role == VardaImageData.METADATA:
                return self._dataParams["Metadata"]
            if role == VardaImageData.BANDS:
                return self._dataParams["Bands"]
            if role == VardaImageData.STRETCH:
                return self._dataParams["Stretch"]

            category_name, _ = self._dataParams[index.row()]
            if role == Qt.ItemDataRole.DisplayRole:
                return category_name
            return None

        # Child rows: parameter key-value pairs
        category_data = index.parent().internalPointer()

    def setData(self, index, value, role = ...):


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


class AbstractImageModelMeta(ABCMeta, type(QtCore.QObject)):
    """
    Metaclass for AbstractImageModel. This needs to exist because QObject and ABC
    use different metaclasses.
    So this makes a metaclass that works for both. Or something like that.
    What is a metaclass? It's a class for classes. It defines how a class behaves.
    Why is that a thing? Because Python is weird.
    """
    pass


class AbstractImageModel(QtCore.QObject, metaclass=AbstractImageModelMeta):
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
