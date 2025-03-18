# standard library
from abc import ABC, abstractmethod
from typing import Tuple
import logging

# third party imports
import numpy as np

# local imports
from core.entities.metadata import Metadata

logger = logging.getLogger(__name__)


class AbstractImageLoader(ABC):  # pylint: disable=too-few-public-methods
    """
    Class to load images from a file path. To be inherited by specific image types.
    Usage:
    loader = ENVIImageLoader("path/to/file")
    imageData = loader.load()
    """

    # dictionary of all subclasses of AbstractImageLoader, mapped to their associated keyword
    subclasses = []

    def __init_subclass__(cls, **kwargs):
        """
        runs whenever a subclass is declared. adds it to the list of available subclasses
        """
        super().__init_subclass__(**kwargs)
        logger.info(f"Adding {cls.__name__} to subclasses")
        AbstractImageLoader.subclasses.append(cls)

    def __init__(self):
        self._filePath = None
        self._rasterData = None
        self._imageMetadata = None

    def load(self, filepath: str) -> Tuple[np.ndarray, Metadata]:
        """Loads the image data and metadata from the file path.

        Args:
            filepath: The file path to the image.

        Returns:
            Tuple[np.ndarray, Metadata]: A tuple with the image raster data and metadata
        """
        self._filePath = filepath

        if self._rasterData is None:
            self._rasterData = self.loadRasterData(self._filePath)

        if self._imageMetadata is None:
            self._imageMetadata = self.loadMetadata(self._rasterData, self._filePath)
        return self._rasterData, self._imageMetadata

    @staticmethod
    @abstractmethod
    def loadRasterData(filePath) -> np.ndarray:
        pass

    @staticmethod
    @abstractmethod
    def loadMetadata(raster, filePath) -> Metadata:
        pass
