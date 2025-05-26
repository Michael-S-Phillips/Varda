# src/core/utilities/load_image/loaders/abstractimageloader.py

# standard library
from abc import ABC, abstractmethod
from typing import Tuple, Optional, Dict, Type
import logging
from pathlib import Path

# third party imports
import numpy as np

# local imports
from core.entities.metadata import Metadata

logger = logging.getLogger(__name__)

# Registry of loaders
LOADER_REGISTRY: Dict[str, Type["AbstractImageLoader"]] = {}


class AbstractImageLoader(ABC):  # pylint: disable=too-few-public-methods
    """
    Class to load images from a file path. To be inherited by specific image types.
    Usage:
    loader = ENVIImageLoader("/path/to/file")
    imageData = loader.load()
    """

    # dictionary of all subclasses of AbstractImageLoader, mapped to their associated keyword
    subclasses = []
    imageType = ()  # Should be overridden by subclasses

    def __init_subclass__(cls, **kwargs):
        """
        runs whenever a subclass is declared. adds it to the list of available subclasses
        """
        super().__init_subclass__(**kwargs)
        logger.info(f"Adding {cls.__name__} to subclasses")
        AbstractImageLoader.subclasses.append(cls)

        # Register the loader for its supported types
        if hasattr(cls, "imageType"):
            for ext in cls.imageType:
                if isinstance(ext, str):
                    LOADER_REGISTRY[ext.lower()] = cls

    def __init__(self):
        self._filePath = None
        self._rasterData = None
        self._imageMetadata = None
        self.loadErrors = []
        self.loading_mode = "full"

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
        self.loadErrors = []

        try:
            load_mode = getattr(self, "loading_mode", "full")
            self._rasterData = self.loadRasterData(
                self._filePath, loading_mode=load_mode
            )
        except Exception as e:
            logger.error(f"Failed to load raster data: {e}")
            raise ValueError(f"Failed to load raster data: {e}")

        try:
            self._imageMetadata = self.loadMetadata(self._rasterData, self._filePath)
        except Exception as e:
            logger.error(f"Error loading metadata: {e}")
            self.loadErrors.append(f"Metadata load error: {e}")
            # Create fallback metadata with basic information
            self._imageMetadata = self.createFallbackMetadata(
                self._rasterData, self._filePath
            )

        return self._rasterData, self._imageMetadata

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
            extraMetadata={
                "warning": "Metadata was created as a fallback due to loading errors"
            },
        )

    @staticmethod
    @abstractmethod
    def loadRasterData(filePath, loading_mode="full") -> np.ndarray:
        """Load raster data from a file.

        Args:
            filePath: Path to the image file
            loading_mode: Mode to control loading ('full', 'preview', or 'metadata')

        Returns:
            np.ndarray: The raster data
        """
        pass

    @staticmethod
    @abstractmethod
    def loadMetadata(raster, filePath) -> Metadata:
        """Load metadata from an image file.

        This abstract method should be implemented by concrete loader classes to extract
        metadata from the image file. The implementation should handle any format-specific
        metadata extraction and return it in a standardized Metadata object.

        Args:
            raster (np.ndarray): The loaded raster data array with shape (height, width, bands)
            filePath (str): Path to the image file

        Returns:
            Metadata: A Metadata object containing the extracted metadata

        Raises:
            ValueError: If metadata cannot be extracted from the file
        """
        pass
