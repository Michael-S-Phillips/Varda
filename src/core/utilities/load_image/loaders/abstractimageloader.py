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
LOADER_REGISTRY: Dict[str, Type['AbstractImageLoader']] = {}

class AbstractImageLoader(ABC):  # pylint: disable=too-few-public-methods
    """
    Class to load images from a file path. To be inherited by specific image types.
    Usage:
    loader = ENVIImageLoader("path/to/file")
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
        if hasattr(cls, 'imageType'):
            for ext in cls.imageType:
                if isinstance(ext, str):
                    LOADER_REGISTRY[ext.lower()] = cls

    def __init__(self):
        self._filePath = None
        self._rasterData = None
        self._imageMetadata = None
        self._loadErrors = []
        self.loading_mode = 'full'

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
            load_mode = getattr(self, 'loading_mode', 'full')
            self._rasterData = self.loadRasterData(self._filePath, loading_mode=load_mode)
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
    def loadRasterData(filePath, loading_mode='full') -> np.ndarray:
        pass

    @staticmethod
    @abstractmethod
    def loadMetadata(raster, filePath) -> Metadata:
        pass
    
    @classmethod
    def get_loader_for_file(cls, file_path: str) -> 'AbstractImageLoader':
        """Get the appropriate loader for a given file path.
        
        Args:
            file_path: Path to the image file
            
        Returns:
            An instance of the appropriate loader
            
        Raises:
            ValueError: If no suitable loader is found
        """
        ext = Path(file_path).suffix.lower()
        
        # Try exact match with registered extensions
        if ext in LOADER_REGISTRY:
            return LOADER_REGISTRY[ext]()
            
        # Fall back to trying content-based detection
        try:
            import magic
            file_mime = magic.from_file(file_path, mime=True)
            
            # Map mime types to potential loaders
            from importlib import import_module
            
            # Map common mime types to loaders
            mime_map = {
                'image/tiff': 'tiffimageloader.TIFFImageLoader',
                'image/jpeg': 'pillowimageloader.PillowImageLoader',
                'image/png': 'pillowimageloader.PillowImageLoader',
                'image/bmp': 'pillowimageloader.PillowImageLoader',
                'image/gif': 'pillowimageloader.PillowImageLoader',
                'application/x-hdf': 'hdf5imageloader.HDF5ImageLoader'
            }
            
            if file_mime in mime_map:
                module_path, class_name = mime_map[file_mime].split('.')
                # Import the module and get the class
                try:
                    module = import_module(f'core.utilities.load_image.loaders.{module_path}')
                    loader_class = getattr(module, class_name)
                    return loader_class()
                except (ImportError, AttributeError) as e:
                    logger.warning(f"Could not import loader for {file_mime}: {e}")
        except ImportError:
            logger.warning("python-magic not available, using extension-based detection only")
        except Exception as e:
            logger.warning(f"Error during content-based detection: {e}")
        
        # Last resort: try each loader's static method to see if it works
        for loader_class in cls.subclasses:
            try:
                # Just try to read a tiny bit to see if it works
                loader_class.loadRasterData(file_path, loading_mode='preview')
                return loader_class()
            except Exception:
                continue
                
        raise ValueError(f"Unsupported file type: {ext}")