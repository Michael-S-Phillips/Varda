# standard library
from dataclasses import dataclass

# third-party imports
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import pyqtSignal
import numpy as np

from models import ImageModel
from models.metadata import Metadata


# local imports


class BaseImageView(QWidget):

    @dataclass
    class ImageModelConfig:
        rasterData : np.ndarray
        metadata : Metadata
        band : dict
        stretch : tuple

        imageSlice : property  # Function to slice the image data
        bandCount : property  # Function to get the number of bands in the image

    def __init__(self, imageModel: ImageModel=None, parent=None):
        super(BaseImageView, self).__init__(parent)

        self.__widget = None
        self.__initUI()


    def __initUI(self):
        """
        Initialize the UI for the View.
         Eventually we may have a base UI for all image views. maybe
         something to select the active image model, band, stretch, etc.
        """
        self.setLayout(QVBoxLayout())

    @property
    def imageModel(self):
        return self.__imageModelSubset

    @imageModel.setter
    def imageModel(self, imageModel):
        self.__mainImageModel = imageModel
        self.__imageModelSubset = self.ImageModelConfig(imageModel.rasterData,
                                                imageModel.metadata,
                                                imageModel.band,
                                                imageModel.stretch,
                                                imageModel.imageSlice,
                                                imageModel.bandCount
                                                )

        self.__linkSignals()

    def __linkSignals(self):
        self.__mainImageModel.sigBandChanged.connect(self.bandChanged)
        self.__mainImageModel.sigStretchChanged.connect(self.stretchChanged)
        self.__mainImageModel.sigImageChanged.connect(self.updateView)

    def setViewLayout(self, layout):
        self.layout().addChildLayout(layout)

    def bandChanged(self):
        pass

    def stretchChanged(self):
        pass

    def updateView(self):
        pass

    def updateModel(self):
        pass

    def setBand(self, value):
        self.imageModel.band = value
