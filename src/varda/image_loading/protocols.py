"""
Protocol for image loaders that can load images from files.
"""

from typing import Protocol, Tuple, runtime_checkable

import numpy as np

from varda.core.entities.metadata import Metadata


@runtime_checkable
class ImageLoaderProtocol(Protocol):
    """
    Protocol for image loaders that can load images from files. All image loaders must implement this Protocol.
    """

    @staticmethod
    def loadRasterData(filePath, loadingMode="full") -> np.ndarray:
        """Load raster data from a file.

        Args:
            filePath: Path to the image file
            loadingMode: Mode to control loading ('full', 'preview', or 'metadata')

        Returns:
            np.ndarray: The raster data
        """

    @staticmethod
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
