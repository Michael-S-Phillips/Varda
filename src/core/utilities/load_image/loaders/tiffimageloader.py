# src/core/utilities/load_image/loaders/tiffimageloader.py

# standard library
import logging
from pathlib import Path

# third party imports
import os

import affine
import numpy as np
import rasterio
from pyproj import CRS
from rasterio.errors import RasterioIOError

from core.entities import GeoReferencer

# local imports
from core.utilities.load_image.loaders.abstractimageloader import AbstractImageLoader
from core.entities import Metadata
from core.entities import Band

logger = logging.getLogger(__name__)


class TIFFImageLoader(AbstractImageLoader):  # pylint: disable=too-few-public-methods
    """Implementation of AbstractImageLoader for TIFF/GeoTIFF Images"""

    imageType = (".tif", ".tiff", ".geotiff", ".gtiff")

    @staticmethod
    def loadRasterData(filePath, loading_mode="full") -> np.ndarray:
        """Load raster data from TIFF file.

        Args:
            filePath: Path to the TIFF file
            loading_mode: 'full', 'preview', or 'metadata'

        Returns:
            np.ndarray: The raster data with shape (height, width, bands)
        """
        try:
            # Check file size
            file_size_mb = os.path.getsize(filePath) / (1024 * 1024)
            is_large_file = file_size_mb > 500 or loading_mode == "preview"

            with rasterio.open(filePath) as src:
                # Determine output shape
                if is_large_file or loading_mode == "preview":
                    # Calculate appropriate downsampling factor
                    if loading_mode == "preview":
                        # Use a fixed preview size for preview mode
                        target_size_mb = 100  # Target a ~100MB preview
                        downsample = max(1, int(np.sqrt(file_size_mb / target_size_mb)))
                    else:
                        # Adaptive downsampling based on file size
                        downsample = max(1, int(file_size_mb / 500))

                    logger.info(
                        f"Loading {loading_mode} with downsampling factor {downsample}"
                    )

                    # Calculate new dimensions
                    out_shape = (
                        src.count,
                        int(src.height / downsample),
                        int(src.width / downsample),
                    )

                    # Read with decimation
                    data = src.read(
                        out_shape=out_shape,
                        masked=True,
                        resampling=rasterio.enums.Resampling.average,
                    )
                else:
                    # For smaller files, read at full resolution
                    data = src.read(masked=True)

                # Transpose to get (height, width, bands) shape
                data = data.transpose(1, 2, 0)

                # If data is masked, fill with zeros (or another appropriate value)
                if hasattr(data, "filled"):
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
                metadata_dict["dataIgnore"] = (
                    src.nodata if src.nodata is not None else 0
                )

                # CRS and transform (for georeferenced images)
                if src.transform != affine.identity and src.crs is not None:
                    transform = src.transform
                    logger.debug(f"Transform:\n{transform}")
                    crs = CRS.from_wkt(src.crs.to_wkt())
                    logger.debug(f"crs:\n{crs}")
                    metadata_dict["geoReferencer"] = GeoReferencer(
                        transform=transform, crs=crs
                    )
                else:
                    logger.debug(f"Image does not contain geospatial information.")

                if src.crs:
                    metadata_dict["crs"] = src.crs.to_string()

                if src.transform:
                    metadata_dict["transform"] = [float(x) for x in src.transform]

                # Try to get wavelength information from tags
                tags = src.tags()
                wavelengths = None

                # Check for ENVI-style wavelength info in tags
                if "wavelength" in tags:
                    try:
                        wavelengths = np.array(
                            [float(w) for w in tags["wavelength"].split(",")]
                        )
                        metadata_dict["wavelengths"] = wavelengths
                        metadata_dict["wavelengths_type"] = float
                        metadata_dict["wavelength_units"] = tags.get(
                            "wavelength_units", "nm"
                        )
                    except (ValueError, TypeError):
                        errors.append(
                            "Could not parse wavelength information from tags"
                        )

                # If no wavelength info, create default wavelengths
                if wavelengths is None:
                    metadata_dict["wavelengths"] = np.arange(src.count)
                    metadata_dict["wavelengths_type"] = int
                    errors.append("No wavelength information found, using band indices")

                # Extract band names if available
                band_names = []
                for i in range(1, src.count + 1):
                    band_name = src.tags(i).get("name", f"Band_{i}")
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
