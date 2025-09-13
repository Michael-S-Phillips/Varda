"""
Pillow Image Loader implementation.
"""

# standard library
import logging

# third party imports
import numpy as np
from PIL import Image as PILImage
from PIL.ExifTags import TAGS

# local imports
from varda.core.entities.metadata import Metadata
from varda.core.entities import Band
from varda.image_loading import registerImageLoader, ImageLoaderProtocol

logger = logging.getLogger(__name__)


@registerImageLoader("Common Image", (".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tga"))
class PillowImageLoader(ImageLoaderProtocol):
    """Implementation of ImageLoader for common image formats using Pillow"""

    @staticmethod
    def loadRasterData(filePath, loading_mode="full") -> np.ndarray:
        """Load raster data from common image formats using Pillow.

        Args:
            filePath: Path to the image file
            loading_mode: 'full', 'preview', or 'metadata'

        Returns:
            np.ndarray: The raster data with shape (height, width, bands)
        """
        try:
            # Open the image
            image = PILImage.open(filePath)

            # Handle preview mode for large images
            if loading_mode == "preview" and (
                image.width > 1000 or image.height > 1000
            ):
                # Calculate resize factor to get a reasonable preview size
                max_dim = max(image.width, image.height)
                resize_factor = max(1, max_dim // 1000)
                new_size = (image.width // resize_factor, image.height // resize_factor)
                image = image.resize(new_size, PILImage.LANCZOS)
                logger.info(f"Loaded preview with resize factor {resize_factor}")

            # Convert to RGB if needed
            if image.mode == "RGBA":
                # Keep alpha channel
                data = np.array(image)
            elif image.mode != "RGB":
                # Convert to RGB
                image = image.convert("RGB")
                data = np.array(image)
            else:
                # Already RGB
                data = np.array(image)

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
            if hasattr(image, "_getexif") and image._getexif():
                exif = image._getexif()
                if exif:
                    for tag_id, value in exif.items():
                        tag = TAGS.get(tag_id, tag_id)
                        # Convert binary data to string representation
                        if isinstance(value, bytes):
                            try:
                                value = value.decode("utf-8")
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
