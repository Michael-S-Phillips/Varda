# standard library

# third-party imports
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import pyqtSignal, pyqtSlot
import numpy as np


# local imports
from src.models.imagemodel import ImageModel
from src.models.imageviewselectionmodel import ImageViewSelectionModel


class BaseImageView(QWidget):
    """
    Base class for image views in the application. This class provides the basic
    structure and functionality for displaying and interacting with image models.
    It will also include common UI elements that all image views will share,
    for selecting bands and stretches.

    NOTE: This class provides many convenience methods for interacting with
    the image model and selection model. Subclasses should use these whenever
    possible, instead of directly interacting with the image model or selection model.
    This is to maintain good encapsulation. If something about the image model or
    selection model changes, we only need to update this class, and not all the subclasses.

    Methods:
        setViewLayout(layout: QVBoxLayout):
            Sets the layout for the view.
        setImageModel(imageModel: ImageModel):
            Sets the image model for the view and links the necessary signals.
        getBand() -> ImageModel.Band:
            Returns the currently selected band from the selection model.
        getStretch() -> ImageModel.Stretch:
            Returns the currently selected stretch from the selection model.
        setBand(r: int, g: int, b: int):
            Sets the values of the currently selected band in the selection model.
        setStretch(minR: int, maxR: int, minG: int, maxG: int, minB: int, maxB: int):
            Sets the values of the currently selected stretch in the selection model.
        getRasterData() -> np.ndarray:
            Returns the raw image data from the image model.
        getRasterDataSlice() -> np.ndarray:
            Returns a 3-band slice of the raster data from the image model, based on the
            view's currently selected band.
        getMetadata() -> Metadata:
            Returns the metadata from the image model.
        imageChanged():
            Slot called when the image model changes. Should be overridden by subclasses.
        bandChanged():
            Slot called when the band selection changes. Should be overridden by subclasses.
        stretchChanged():
            Slot called when the stretch selection changes. Should be overridden by subclasses.    """

    def __init__(self, imageModel: ImageModel=None, parent=None):
        """
        Initializes the BaseImageView with an optional image model and parent.

        Args:
            imageModel (ImageModel, optional): The image model to associate with this view.
            parent (QWidget, optional): The parent widget. Defaults to None.
        """
        super().__init__(parent)
        self.__layout = None
        self.__subclassUI = None
        self.__initUI()

        self._imageModel = None
        self._selectionModel = None
        if imageModel:
            self.setImageModel(imageModel)

    def __initUI(self):
        """
        Initialize the BaseUI for the view.
        This exists because eventually we will have a common UI for all views.
            such as a way to select the active band and stretch.
        """
        self.__layout = QVBoxLayout()
        self.__layout.setContentsMargins(0, 0, 0, 0)  # Set margins to 0

        self.__subclassUI = QWidget()
        # self.__layout.addWidget(self.__subclassUI)
        self.setLayout(self.__layout)

    def setViewLayout(self, layout):
        """
        This is to be used by subclasses to add their UI to the view.

        Args:
            layout (QVBoxLayout): The layout to set for the view.
        """
        self.__layout.addLayout(layout)
        # self.__subclassUI.setLayout(layout)

    def setImageModel(self, imageModel):
        """
        Sets the image model for the view and links the necessary signals.

        Args:
            imageModel (ImageModel): The image model to associate with this view.
        """
        self._imageModel = imageModel
        self._selectionModel = ImageViewSelectionModel(self._imageModel)
        self._linkSignals()

        self.imageChanged()

    def _linkSignals(self):
        """
        Links the signals from the image model and selection model to the view's slots.
        """
        self._imageModel.sigImageChanged.connect(self.imageChanged)

        self._selectionModel.sigBandChanged.connect(self.bandChanged)
        self._selectionModel.sigStretchChanged.connect(self.stretchChanged)

    def getBand(self) -> ImageModel.Band:
        """
        Returns the currently selected band from the selection model.

        Returns:
            ImageModel.Band: The currently selected band.
        """
        return self._selectionModel.currentBand()

    def getStretch(self) -> ImageModel.Stretch:
        """
        Returns the currently selected stretch from the selection model.

        Returns:
            ImageModel.Stretch: The currently selected stretch.
        """
        return self._selectionModel.currentStretch()

    def setBand(self, r, g, b):
        """
        Sets the values of the currently selected band in the selection model.

        Args:
            r (int): The red band value.
            g (int): The green band value.
            b (int): The blue band value.
        """
        self._selectionModel.setBandValues(r, g, b)

    def setStretch(self, minR, maxR, minG, maxG, minB, maxB):
        """
        Sets the values of the currently selected stretch in the selection model.

        Args:
            minR (int | float): The minimum red stretch value.
            maxR (int | float): The maximum red stretch value.
            minG (int | float): The minimum green stretch value.
            maxG (int | float): The maximum green stretch value.
            minB (int | float): The minimum blue stretch value.
            maxB (int | float): The maximum blue stretch value.
        """
        self._selectionModel.setStretchValues(minR, maxR, minG, maxG, minB, maxB)

    def getRasterData(self):
        """
        Returns the raw image data from the image model.

        Returns:
            np.ndarray: The raw image data.
        """
        return self._imageModel.rasterData

    def getRasterDataSlice(self):
        """
        Returns a 3 band slice of the raster data from the image model, based on the
        view's currently selected band.

        Returns:
            np.ndarray: The raster data slice.
        """
        return self._imageModel.getRasterDataSlice(self.getBand().values)

    def getMetadata(self):
        """
        Returns the metadata from the image model.

        Returns:
            Metadata: The metadata for the image model.
        """
        return self._imageModel.metadata

    @pyqtSlot()
    def imageChanged(self):
        """
        Convenience method for subclasses to override.
            This method is called when anything about the image model changes
        """
        pass

    @pyqtSlot()
    def bandChanged(self):
        """
        Convenience method for subclasses to override.
            This method is called when either the selected band data changes,
            or a new band is selected.
        """
        pass

    @pyqtSlot()
    def stretchChanged(self):
        """
        Convenience method for subclasses to override.
            This method is called when either the selected stretch data changes,
            or a new stretch is selected.
        """
        pass
