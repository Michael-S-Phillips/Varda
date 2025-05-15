# src/core/utilities/load_image/loaders/image_loaders.py (new consolidated file)

import logging
import numpy as np
from typing import Dict, Type, List
from pathlib import Path
import os

# third party imports
from PIL import Image as PILImage
from PIL.ExifTags import TAGS
import rasterio

# local imports
from core.utilities.load_image.loaders.abstractimageloader import AbstractImageLoader
from core.entities.metadata import Metadata
from core.entities import Band

logger = logging.getLogger(__name__)

# Dictionary mapping file extensions to loader classes
LOADERS: Dict[str, Type[AbstractImageLoader]] = {}

def register_loader(cls):
    """Decorator to register a loader class for specific file extensions."""
    for ext in cls.imageType:
        LOADERS[ext.lower()] = cls
    return cls

@register_loader
class TIFFImageLoader(AbstractImageLoader):  # pylint: disable=too-few-public-methods
    """Implementation of AbstractImageLoader for TIFF/GeoTIFF Images"""

    imageType = (".tif", ".tiff", ".geotiff", ".gtiff")

    @staticmethod
    def loadRasterData(filePath, loading_mode='full') -> np.ndarray:
        """Load raster data from TIFF file.
        
        Args:
            filePath: Path to the TIFF file
            loading_mode: 'full', 'preview', or 'metadata'
            
        Returns:
            np.ndarray: The raster data with shape (height, width, bands)
            
        Raises:
            ValueError: If the file cannot be read
        """
        try:
            # Check file size
            file_size_mb = os.path.getsize(filePath) / (1024 * 1024)
            is_large_file = file_size_mb > 500 or loading_mode == 'preview'
            
            with rasterio.open(filePath) as src:
                # Determine output shape
                if is_large_file or loading_mode == 'preview':
                    # Calculate appropriate downsampling factor
                    if loading_mode == 'preview':
                        # Use a fixed preview size for preview mode
                        target_size_mb = 100  # Target a ~100MB preview
                        downsample = max(1, int(np.sqrt(file_size_mb / target_size_mb)))
                    else:
                        # Adaptive downsampling based on file size
                        downsample = max(1, int(file_size_mb / 500))
                    
                    logger.info(f"Loading {loading_mode} with downsampling factor {downsample}")
                    
                    # Calculate new dimensions
                    out_shape = (
                        src.count,
                        int(src.height / downsample),
                        int(src.width / downsample)
                    )
                    
                    # Read with decimation
                    data = src.read(
                        out_shape=out_shape,
                        masked=True,
                        resampling=rasterio.enums.Resampling.average
                    )
                else:
                    # For smaller files, read at full resolution
                    data = src.read(masked=True)
                
                # Transpose to get (height, width, bands) shape
                data = data.transpose(1, 2, 0)
                
                # If data is masked, fill with zeros (or another appropriate value)
                if hasattr(data, 'filled'):
                    data = data.filled(0)
                
                return data
                
        except rasterio.errors.RasterioIOError as e:
            logger.error(f"Failed to load TIFF file {filePath}: {e}")
            raise ValueError(f"Could not read TIFF file: {e}")
        except Exception as e:
            logger.error(f"Unexpected error loading TIFF file {filePath}: {e}")
            raise ValueError(f"Error processing TIFF file: {e}")

    @staticmethod
    def loadMetadata(raster, filePath) -> Metadata:
        """Extract metadata from TIFF file.
        
        Args:
            raster: The raster data
            filePath: Path to the TIFF file
            
        Returns:
            Metadata: The metadata for the image
        """
        metadata_dict = {}
        errors = []

        try:
            with rasterio.open(filePath) as src:
                # Basic metadata
                metadata_dict["filePath"] = filePath
                metadata_dict["driver"] = src.driver
                metadata_dict["width"] = src.width
                metadata_dict["height"] = src.height
                metadata_dict["bandCount"] = src.count
                metadata_dict["resolution"] = src.res
                metadata_dict["dtype"] = str(src.dtypes[0])
                
                # Handle nodata value
                metadata_dict["dataIgnore"] = src.nodata if src.nodata is not None else 0
                
                # CRS and transform (for georeferenced images)
                if src.crs:
                    metadata_dict["crs"] = src.crs.to_string()
                
                if src.transform:
                    metadata_dict["transform"] = [float(x) for x in src.transform]
                
                # Try to get wavelength information from tags
                tags = src.tags()
                wavelengths = None
                
                # Check for ENVI-style wavelength info in tags
                if 'wavelength' in tags:
                    try:
                        wavelengths = np.array([float(w) for w in tags['wavelength'].split(',')])
                        metadata_dict["wavelengths"] = wavelengths
                        metadata_dict["wavelengths_type"] = float
                        metadata_dict["wavelength_units"] = tags.get('wavelength_units', 'nm')
                    except (ValueError, TypeError):
                        errors.append("Could not parse wavelength information from tags")
                
                # If no wavelength info, create default wavelengths
                if wavelengths is None:
                    metadata_dict["wavelengths"] = np.arange(src.count)
                    metadata_dict["wavelengths_type"] = int
                    errors.append("No wavelength information found, using band indices")
                
                # Extract band names if available
                band_names = []
                for i in range(1, src.count + 1):
                    band_name = src.tags(i).get('name', f"Band_{i}")
                    band_names.append(band_name)
                
                if band_names:
                    metadata_dict["band_names"] = band_names
                
                # Create default band
                if src.count >= 3:
                    # Use RGB bands if we have at least 3
                    metadata_dict["defaultBand"] = Band("default", 0, 1, 2)
                else:
                    # Use the first band for all channels if we have fewer than 3
                    metadata_dict["defaultBand"] = Band("default", 0, 0, 0)
                
                # Add all tags as extra metadata
                extraMetadata = {}
                for key, value in tags.items():
                    extraMetadata[key] = value
                
                # Add any errors
                if errors:
                    extraMetadata["loadErrors"] = errors
                
                metadata_dict["extraMetadata"] = extraMetadata

        except Exception as e:
            logger.error(f"Error extracting metadata from TIFF: {e}")
            raise ValueError(f"Failed to extract metadata: {e}")

        try:
            return Metadata(**metadata_dict)
        except Exception as e:
            logger.error(f"Error creating Metadata object: {e}")
            raise ValueError(f"Could not create metadata object: {e}")
        
@register_loader
class PillowImageLoader(AbstractImageLoader):  # pylint: disable=too-few-public-methods
    """Implementation of AbstractImageLoader for common image formats using Pillow"""

    imageType = (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tga")

    @staticmethod
    def loadRasterData(filePath) -> np.ndarray:
        """Load raster data from common image formats using Pillow.
        
        Args:
            filePath: Path to the image file
            
        Returns:
            np.ndarray: The raster data with shape (height, width, bands)
            
        Raises:
            ValueError: If the file cannot be read
        """
        try:
            # Open the image
            image = PILImage.open(filePath)
            
            # Convert to RGB if needed
            if image.mode == 'RGBA':
                # Keep alpha channel
                data = np.array(image)
            elif image.mode != 'RGB':
                # Convert to RGB
                image = image.convert('RGB')
                data = np.array(image)
            else:
                # Already RGB
                data = np.array(image)
            
            # Ensure we have a 3D array (height, width, bands)
            if len(data.shape) == 2:
                # Single band (grayscale) - reshape to (height, width, 1)
                data = data.reshape(data.shape[0], data.shape[1], 1)
            
            return data
            
        except Exception as e:
            logger.error(f"Failed to load image file {filePath}: {e}")
            raise ValueError(f"Could not read image file: {e}")

    @staticmethod
    def loadMetadata(raster, filePath) -> Metadata:
        """Extract metadata from image file.
        
        Args:
            raster: The raster data
            filePath: Path to the image file
            
        Returns:
            Metadata: The metadata for the image
        """
        metadata_dict = {}
        errors = []

        try:
            # Open the image to extract metadata
            image = PILImage.open(filePath)
            
            # Basic metadata
            metadata_dict["filePath"] = filePath
            metadata_dict["driver"] = f"Pillow-{image.format}"
            metadata_dict["width"] = image.width
            metadata_dict["height"] = image.height
            metadata_dict["dtype"] = str(raster.dtype)
            metadata_dict["dataIgnore"] = 0  # Default for RGB images
            
            # Determine band count
            if len(raster.shape) == 3:
                metadata_dict["bandCount"] = raster.shape[2]
            else:
                metadata_dict["bandCount"] = 1
            
            # Set wavelengths to band indices (RGB images don't have wavelength info)
            metadata_dict["wavelengths"] = np.arange(metadata_dict["bandCount"])
            metadata_dict["wavelengths_type"] = int
            
            # For RGB images, set appropriate band names
            band_names = []
            if metadata_dict["bandCount"] == 3:
                band_names = ["Red", "Green", "Blue"]
            elif metadata_dict["bandCount"] == 4:
                band_names = ["Red", "Green", "Blue", "Alpha"]
            else:
                band_names = [f"Band_{i}" for i in range(metadata_dict["bandCount"])]
            
            # Set default band configuration for RGB
            if metadata_dict["bandCount"] >= 3:
                metadata_dict["defaultBand"] = Band("default", 0, 1, 2)
            else:
                metadata_dict["defaultBand"] = Band("default", 0, 0, 0)
            
            # Extract EXIF data if available
            extraMetadata = {}
            if hasattr(image, '_getexif') and image._getexif():
                exif = image._getexif()
                if exif:
                    for tag_id, value in exif.items():
                        tag = TAGS.get(tag_id, tag_id)
                        # Convert binary data to string representation
                        if isinstance(value, bytes):
                            try:
                                value = value.decode('utf-8')
                            except UnicodeDecodeError:
                                value = str(value)
                        extraMetadata[f"exif_{tag}"] = str(value)
            
            # Add image info
            extraMetadata["format"] = image.format
            extraMetadata["mode"] = image.mode
            
            # Add any errors
            if errors:
                extraMetadata["loadErrors"] = errors
            
            metadata_dict["extraMetadata"] = extraMetadata

        except Exception as e:
            logger.error(f"Error extracting metadata from image: {e}")
            raise ValueError(f"Failed to extract metadata: {e}")

        try:
            return Metadata(**metadata_dict)
        except Exception as e:
            logger.error(f"Error creating Metadata object: {e}")
            raise ValueError(f"Could not create metadata object: {e}")

def get_loader_for_file(file_path: str) -> AbstractImageLoader:
    """Get the appropriate loader for a given file path."""
    ext = Path(file_path).suffix.lower()
    
    # Try exact match with registered extensions
    if ext in LOADERS:
        return LOADERS[ext]()
        
    # Fall back to content-based detection if needed
    # ...
    
    raise ValueError(f"Unsupported file type: {ext}")