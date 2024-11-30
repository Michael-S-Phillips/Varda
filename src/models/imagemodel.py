# standard library
import logging

# third party imports
from PyQt6.QtCore import QObject, pyqtSignal, Qt, pyqtSlot
import pyqtgraph as pg
import numpy as np

# local imports
from models.tablemodel import TableModel
from models.metadata import Metadata

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

        self._metadataTable = None
        self._bandTable = None
        self._stretchTable = None
        self._ROITable = None

        self.initInnerModels(defaults)

        self._rasterData = rasterData

        self._imageData = [self._rasterData, self._metadataTable, self._bandTable,
                           self._stretchTable, self._ROITable]
        self._header = ["Raster Data", "Metadata", "Band", "Stretch", "ROI"]

    def initInnerModels(self, defaults=None):
        """
        Initialize inner models for band, stretch, metadata, and ROI tables.

        Args:
            defaults (dict, optional): Default settings for band, stretch, and other
            tables. Primarily used for testing.
        """
        if defaults is None:
            defaults = {}

        bandColumnHeader, bandData = defaults["band"] if defaults.get("band") else \
            (["r", "g", "b"], {"mono": [0, 0, 0],
                               "rgb": [0, 1, 2],
                               "custom1": [10, 20, 30]}
             )
        self._bandTable = TableModel(bandColumnHeader, bandData)

        stretchColumnHeader, stretchData = defaults["stretch"] if defaults.get("stretch") else \
            (["minR", "maxR", "minG", "maxG", "minB", "maxB"],
             {"defaultfloat": [0, 1, 0, 1, 0, 1],
              "defaultuint8": [0, 255, 0, 255, 0, 255]}
             )
        self._stretchTable = TableModel(stretchColumnHeader, stretchData)
        metadataHeader, metadataData = (["Name", "Value"],
                                        self._metadata.__dict__)
        metadataData = {key: [value] for key, value in metadataData.items()}
        self._metadataTable = TableModel(metadataHeader, metadataData)

        self._ROITable = TableModel()

    """
    Properties:
        rasterData (np.ndarray): The raw image data.
        metadataTable (TableModel): Table model for metadata.
        metadata (Metadata): Metadata associated with the image.
        bandTable (TableModel): Table model for band adjustments.
        stretchTable (TableModel): Table model for stretch adjustments.
        ROITable (TableModel): Table model for ROI adjustments.
        imageSlice (np.ndarray): The image slice for the first band.
        normalized_data (np.ndarray): The normalized
    """
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
    def metadataTable(self) -> TableModel:
        """
        Get the metadata table model.

        Returns:
            TableModel: The metadata.
        """
        return self._metadataTable

    @property
    def bandTable(self) -> TableModel:
        """
        Get the band table model.

        Returns:
            TableModel: The band table model.
        """
        return self._bandTable

    @property
    def stretchTable(self) -> TableModel:
        """
        Get the stretch table model.

        Returns:
            TableModel: The stretch table model.
        """
        return self._stretchTable

    @property
    def ROITable(self) -> TableModel:
        """
        Get the ROI table model.

        Returns:
            TableModel: The ROI table model.
        """
        return self._ROITable

    @property
    def imageSlice(self) -> np.ndarray:
        """
        Get a slice of the image data based on the band settings.

        Returns:
            np.ndarray: The image slice.
        """
        try:
            # hardcoded to get the first band for now
            index = self._bandTable.index(0, 0)
            bandData = self._bandTable.getRow(index)
            return self.rasterData[:, :, bandData]
        except TypeError:
            msg = "Error getting imageSlice"
            logger.exception(msg)
            raise None

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
