# standard library
from abc import ABC, abstractmethod
from typing import Tuple
import logging

# third party imports
import numpy as np

# local imports
from core.entities.metadata import Metadata

logger = logging.getLogger(__name__)


class AbstractImageLoader(ABC):
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

    def __init__(self, filepath=None):
        self._filePath = filepath
        if self._filePath is None:
            logger.warning("No file path provided")
        self._rasterData = None
        self._imageMetadata = None

    def load(self, filepath=None) -> Tuple[np.ndarray, Metadata] | None:
        if filepath:
            self._filePath = filepath
        if self._filePath is None:
            logger.error("No file path provided")
            return None

        if self._rasterData is None:
            self._rasterData = self._loadRasterData(self._filePath)

        if self._imageMetadata is None:
            self._imageMetadata = self._loadMetadata(self._rasterData, self._filePath)

        return self._rasterData, self._imageMetadata

    @staticmethod
    @abstractmethod
    def _loadRasterData(filePath) -> np.ndarray:
        pass

    @staticmethod
    @abstractmethod
    def _loadMetadata(image, filePath) -> Metadata:
        pass
