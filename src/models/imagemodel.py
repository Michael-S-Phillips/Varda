# standard library
import logging

# third party imports
# pylint: disable=no-name-in-module
from PyQt6.QtCore import QObject, pyqtSignal, Qt, pyqtSlot
import pyqtgraph as pg
import numpy as np

# local imports
from models.parametermodel import ParameterModel
from .tablemodel import TableModel
from .metadata import Metadata
from .observablelist import ObservableList
from .parametermodel import ParameterModel

logger = logging.getLogger(__name__)


class ImageModel(QObject):
    """
    Base model for images in varda.
    Allows for a consistent interface with the images. Provides a set of signals and
    slots for information exchange between the image and other views.

    Attributes:
        _rasterData (np.ndarray): The raster data of the image.
        _metadata (Metadata): The metadata of the image.
        _metadataTable (TableModel): Table model for metadata.
        _bandTable (TableModel): Table model for band adjustments.
        _stretchTable (TableModel): Table model for stretch adjustments.
        _ROITable (TableModel): Table model for ROI adjustments.
    """

    roiChanged = pyqtSignal()  # Signal when ROI changes
    bandChanged = pyqtSignal()  # Signal when band adjustments change
    stretchChanged = pyqtSignal()  # Signal when the stretch changes
    imageChanged = pyqtSignal()  # Signal when anything about the image changes
    imageDestroyed = pyqtSignal()  # Signal when the image is destroyed

    def __init__(self, rasterData, metadata, defaults=None):
        """
        Initialize the ImageModel with raster data, metadata, and optional defaults.

        Args:
            rasterData (np.ndarray): The raw image data.
            metadata (Metadata): Metadata associated with the image.
            defaults (dict, optional): Default settings for band, stretch, and other
            tables. Primarily used for testing.
        """
        super().__init__()

        # probably won't keep this
        self._normalized_data = None

        self._rasterData = rasterData
        self._metadata = metadata

        # self._metadataTable = None
        # self._bandTable = None
        # self._stretchTable = None
        # self._ROITable = None
        # self.initInnerModels(defaults)

        self.stretch = [(0, 1), (0, 1), (0, 1)]
        self.band = {"r": 0, "g": 1, "b": 2}

        self.connectSignals()

    def connectSignals(self):
        """
        Connect signals to slots for the image model.
        """
        self.bandChanged.connect(self.imageChanged.emit)
        self.stretchChanged.connect(self.imageChanged.emit)
        self.roiChanged.connect(self.imageChanged.emit)

    @property
    def rasterData(self) -> np.ndarray:
        """
        Get the raster data of the image.
        """
        return self._rasterData

    @property
    def metadata(self) -> Metadata:
        """
        Get the metadata of the image.

        Returns:
            Metadata: The metadata.
        """
        return self._metadata

    @property
    def stretch(self):
        """
        Get the levels of the image.

        Returns:
            tuple: The levels of the image.
        """
        return self._stretch

    @stretch.setter
    def stretch(self, stretch):
        """
        Set the levels of the image.

        Args:
            levels (tuple): The levels of the image.
        """
        self._stretch = stretch
        self.stretchChanged.emit()
        logger.info(f"Stretch changed to {stretch}")

    @property
    def band(self):
        """
        Get the bands of the image.

        Returns:
            dict: The bands of the image.
        """
        return self._band

    @band.setter
    def band(self, band):
        """
        Set the bands of the image.

        Args:
            bands (dict): The bands of the image.
        """
        if isinstance(band, list):
            logger.warning("Band should be a dict, not a list")
            band = {"r": band[0], "g": band[1], "b": band[2]}
        band = {key: int(value) for key, value in band.items()}

        self._band = band
        self.bandChanged.emit()
        logger.info(f"Band changed to {band}")

    @property
    def bandCount(self) -> int:
        """
        Get the number of bands in the image.

        Returns:
            int: The number of bands.
        """
        return self.rasterData.shape[2]

    @property
    def imageSlice(self) -> np.ndarray:
        """
        Get a slice of the image data based on the band settings.

        Returns:
            np.ndarray: The image slice.
        """
        try:
            return self.rasterData[:, :, list(self.band.values())]
        except TypeError:
            msg = "Error getting imageSlice"
            logger.exception(msg)
            raise TypeError

    # @property
    # def imageSlice(self) -> np.ndarray:
    #     """
    #     Get a slice of the image data based on the band settings.
    #
    #     Returns:
    #         np.ndarray: The image slice.
    #     """
    #     try:
    #         # hardcoded to get the first band for now
    #         index = self._bandTable.index(0, 0)
    #         bandData = self._bandTable.getRow(index)
    #         return self.rasterData[:, :, bandData]
    #     except TypeError:
    #         msg = "Error getting imageSlice"
    #         logger.exception(msg)
    #         raise None

    # ignore everything below here for now. too complicated lmao

    # def initInnerModels(self, defaults=None):
    #     """
    #     Initialize inner models for band, stretch, metadata, and ROI tables.
    #
    #     Args:
    #         defaults (dict, optional): Default settings for band, stretch, and other
    #         tables. Primarily used for testing.
    #     """
    #     if defaults is None:
    #         defaults = {}
    #
    #     bandData = {"mono": {"r": 0, "g": 0, "b": 0},
    #                 "rgb": {"r": 0, "g": 1, "b": 2},
    #                 "custom1": {"r": 10, "g": 20, "b": 30}}
    #     self._bandParameters = ParameterModel(bandData)
    #
    #     stretchData = defaults["band"] if defaults.get("band") else \
    #         {"defaultfloat": {"minR": 0, "maxR": 0,
    #                           "minG": 0, "maxG": 0,
    #                           "minB": 0, "maxB": 0},
    #          "defaultuint8": {"minR": 0, "maxR": 255,
    #                           "minG": 0, "maxG": 255,
    #                           "minB": 0, "maxB": 255}
    #          }
    #     self._stretchParameters = ParameterModel(stretchData)
    #
    #     metadataParamData = {"metadata": {key: [value] for key, value in
    #                                       self._metadata.__dict__.items()}}
    #     self._metadataParameters = ParameterModel(metadataParamData)
    #
    #     self._ROITable = TableModel()
    #
    # """
    # Properties:
    #     rasterData (np.ndarray): The raw image data.
    #     metadataTable (TableModel): Table model for metadata.
    #     metadata (Metadata): Metadata associated with the image.
    #     bandTable (TableModel): Table model for band adjustments.
    #     stretchTable (TableModel): Table model for stretch adjustments.
    #     ROITable (TableModel): Table model for ROI adjustments.
    #     imageSlice (np.ndarray): The image slice for the first band.
    #     normalized_data (np.ndarray): The normalized
    # """
    #
    #
    # @property
    # def metadataTable(self) -> TableModel:
    #     """
    #     Get the metadata table model.
    #
    #     Returns:
    #         TableModel: The metadata.
    #     """
    #     return self._metadataTable
    #
    # @property
    # def bandParameters(self) -> ParameterModel:
    #     """
    #     Get the band parameters.
    #
    #     Returns:
    #         ParameterModel: The band parameters.
    #     """
    #     return self._bandParameters
    #
    # @property
    # def bandTable(self) -> TableModel:
    #     """
    #     Get the band table model.
    #
    #     Returns:
    #         TableModel: The band table model.
    #     """
    #     return self._bandTable
    #
    # @property
    # def stretchTable(self) -> TableModel:
    #     """
    #     Get the stretch table model.
    #
    #     Returns:
    #         TableModel: The stretch table model.
    #     """
    #     return self._stretchTable
    #
    # @property
    # def ROITable(self) -> TableModel:
    #     """
    #     Get the ROI table model.
    #
    #     Returns:
    #         TableModel: The ROI table model.
    #     """
    #     return self._ROITable

    def imageItem(self):
        """
        Get a pyqtgraph ImageItem for the image slice.

        Returns:
            pg.ImageItem: The ImageItem.
        """
        return pg.ImageItem(self.imageSlice, levels=(0, 1))

    @property
    def normalized_data(self):
        """
        Get the normalized data of the image.

        Returns:
            np.ndarray: The normalized data.
        """
        if self._normalized_data is not None:
            return self._normalized_data

        self._normalized_data = ((self.rasterData - np.min(self.rasterData)) /
                                 (np.max(self.rasterData) - np.min(self.rasterData)))
        return self._normalized_data

    @pyqtSlot()
    def process(self, process):
        """
        Execute a process on the image.

        Args:
            process: The process to execute.
        """
        pass

    def __str__(self):
        """
        Get the string representation of the class.

        Returns:
            str: The string representation of the class.
        """
        return "name: " + self.__class__.__name__

    def __repr__(self):
        """
        Get the string representation of the class for debugging.
        (for now just the same as __str__)

        Returns:
            str: The string representation of the class for debugging.
        """
        return self.__str__()

    def __del__(self):
        """
        Emit the imageDestroyed signal when the object is deleted. So any views
        dependent on this can clean up.
        """
        self.imageDestroyed.emit()
