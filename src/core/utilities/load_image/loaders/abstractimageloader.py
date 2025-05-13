# standard library
from abc import ABC, abstractmethod
from typing import Tuple, Optional
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
        self._loadErrors = []

    def load(self, filepath: str) -> Tuple[np.ndarray, Metadata]:
        """Loads the image data and metadata from the file path.

        Args:
            filepath: The file path to the image.

        Returns:
            Tuple[np.ndarray, Metadata]: A tuple with the image raster data and metadata
            
        Raises:
            ValueError: If the raster data cannot be loaded, since this is a critical failure.
            For metadata errors, it will attempt to create fallback metadata.
        """
        self._filePath = filepath
        self._loadErrors = []

        try:
            self._rasterData = self.loadRasterData(self._filePath)
        except Exception as e:
            logger.error(f"Failed to load raster data: {e}")
            raise ValueError(f"Failed to load raster data: {e}")

        try:
            self._imageMetadata = self.loadMetadata(self._rasterData, self._filePath)
        except Exception as e:
            logger.error(f"Error loading metadata: {e}")
            self._loadErrors.append(f"Metadata load error: {e}")
            # Create fallback metadata with basic information
            self._imageMetadata = self.createFallbackMetadata(self._rasterData, self._filePath)
            
        return self._rasterData, self._imageMetadata

    def getLoadErrors(self):
        """Returns any errors that occurred during loading."""
        return self._loadErrors

    def createFallbackMetadata(self, raster, filePath):
        """Creates basic metadata when the normal loading process fails."""
        logger.warning("Creating fallback metadata due to loading errors")
        
        # Get basic information from the raster that should always be available
        try:
            height, width, bandCount = raster.shape
        except ValueError:
            # Handle case where raster is 2D instead of 3D
            height, width = raster.shape
            bandCount = 1
            # Convert to 3D for consistency
            raster = raster.reshape(height, width, 1)
            
        return Metadata(
            filePath=filePath,
            driver="Unknown",
            width=width,
            height=height,
            dtype=str(raster.dtype),
            dataIgnore=0,
            bandCount=bandCount,
            wavelengths=np.arange(bandCount),
            wavelengths_type=int,
            extraMetadata={"warning": "Metadata was created as a fallback due to loading errors"}
        )

    @staticmethod
    @abstractmethod
    def loadRasterData(filePath) -> np.ndarray:
        pass

    @staticmethod
    @abstractmethod
    def loadMetadata(raster, filePath) -> Metadata:
        pass