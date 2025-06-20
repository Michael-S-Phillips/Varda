# varda/core/utilities/load_image/loaders/enviimageloader.py

# standard library
import time
import logging
import os

# third party imports
import numpy as np
import rasterio as rio

# local imports
from varda.core.utilities.load_image.loaders import AbstractImageLoader
from varda.core.entities import Metadata, Band
from varda.core.utilities import debug

logging.getLogger("rasterio").setLevel(logging.CRITICAL)

logger = logging.getLogger(__name__)


class ENVIImageLoader(AbstractImageLoader):  # pylint: disable=too-few-public-methods
    """Implementation of AbstractImageLoader for ENVI Images"""

    imageType = (".hdr", ".img")

    @staticmethod
    def loadRasterData(filePath, loading_mode="full") -> np.ndarray:
        """Load raster data from an ENVI image file.

        Args:
            filePath: Path to the ENVI header file
            loading_mode: Mode to control how the data is loaded ('full', 'preview', or 'metadata')

        Returns:
            np.ndarray: The raster data
        """
        path = filePath.replace(".hdr", ".img")
        timeStarted = time.time()

        try:
            with rio.open(path) as src:
                logger.debug("time to open file: %s", time.time() - timeStarted)

                # Check if we should load a downsampled version for preview mode
                if loading_mode == "preview":
                    # Calculate dimensions for preview
                    file_size_mb = os.path.getsize(path) / (1024 * 1024)
                    downsample_factor = max(
                        1, int(file_size_mb / 100)
                    )  # Adjust divisor as needed

                    logger.info(
                        f"Loading preview with downsample factor {downsample_factor}"
                    )

                    # Calculate new dimensions
                    out_shape = (
                        src.count,
                        max(1, int(src.height / downsample_factor)),
                        max(1, int(src.width / downsample_factor)),
                    )

                    # Read with decimation
                    data = src.read(
                        out_shape=out_shape,
                        masked=True,
                        resampling=rio.enums.Resampling.average,
                    )
                else:
                    # Full resolution data
                    timeStarted = time.time()
                    data = src.read(masked=True)
                    logger.debug("time to read data: %s", time.time() - timeStarted)

                # Transpose to match expected format (height, width, bands)
                data = data.transpose(1, 2, 0)

                return data

        except Exception as e:
            logger.error(f"Failed to load raster data from {path}: {e}")
            raise ValueError(f"Could not read image file: {e}")

    @staticmethod
    def loadMetadata(raster, filePath) -> Metadata:  # pylint: disable=too-many-locals
        """Load metadata from an ENVI image file.

        Args:
            raster: The raster data
            filePath: Path to the ENVI header file

        Returns:
            Metadata: The image metadata
        """
        path = filePath.replace(".hdr", ".img")
        metadata_dict = {}
        errors = []

        try:
            with rio.open(path) as src:
                # Basic metadata that should always be available
                metadata_dict["driver"] = src.driver
                metadata_dict["width"] = src.width
                metadata_dict["height"] = src.height
                metadata_dict["bandCount"] = src.count
                metadata_dict["resolution"] = src.res
                metadata_dict["filePath"] = filePath

                # # TODO: Im not totally sure if these are the correct conditions to be looking for
                # if varda.transform != affine.identity and varda.crs is not None:
                #     transform = varda.transform
                #     logger.debug(f"Transform:\n{transform}")
                #     crs = varda.crs.to_wkt() if varda.crs else None
                #     logger.debug(f"crs:\n{crs}")
                #     metadata_dict["transform"] = transform
                #     metadata_dict["crs"] = crs
                #     # metadata_dict["geoReferencer"] = GeoReferencer(
                #     #     transform=transform, crs=crs
                #     # )
                # else:
                #     logger.debug(f"Image does not contain geospatial information.")
                # Optional metadata that might not be available
                try:
                    metadata_dict["dtype"] = src.dtypes[0]
                except (IndexError, AttributeError):
                    metadata_dict["dtype"] = str(raster.dtype)
                    errors.append(
                        "Could not determine dtype from source, using raster dtype"
                    )

                try:
                    metadata_dict["dataIgnore"] = (
                        src.nodata if src.nodata is not None else 0
                    )
                except (AttributeError, IndexError):
                    metadata_dict["dataIgnore"] = 0
                    errors.append("Could not determine nodata value, using 0")

                try:
                    metadata_dict["crs"] = src.crs.to_wkt()
                except (AttributeError, ValueError):
                    errors.append("Could not determine coordinate reference system")

                try:
                    metadata_dict["transform"] = src.transform
                except (AttributeError, ValueError):
                    errors.append("Could not determine geotransform")

                # Get ENVI-specific metadata
                try:
                    enviData = src.tags(ns="ENVI")
                    if debug.DEBUG:
                        logger.debug("Raw Metadata: %s", enviData)
                except:
                    enviData = {}
                    errors.append("Could not read ENVI-specific metadata")

                # Extract description
                try:
                    description = enviData.get("description", "").strip("{}")
                    metadata_dict["description"] = description
                except:
                    errors.append("Could not parse description metadata")

                # Extract default bands
                try:
                    defaultBands = enviData.get("default_bands")
                    if defaultBands:
                        defaultBands = [
                            int(band)
                            for band in enviData["default_bands"].strip("{}").split(",")
                        ]
                        metadata_dict["defaultBand"] = Band(
                            "default", defaultBands[0], defaultBands[1], defaultBands[2]
                        )
                    else:
                        # Set reasonable default bands if not specified
                        if raster.shape[2] >= 3:
                            metadata_dict["defaultBand"] = Band("default", 0, 1, 2)
                        else:
                            metadata_dict["defaultBand"] = Band("default", 0, 0, 0)
                except:
                    # Create a sensible default
                    if raster.shape[2] >= 3:
                        metadata_dict["defaultBand"] = Band("default", 0, 1, 2)
                    else:
                        metadata_dict["defaultBand"] = Band("default", 0, 0, 0)
                    errors.append("Could not parse default bands, using fallback")

                # Extract wavelength units
                try:
                    wavelengthUnits = enviData.get("wavelength_units")
                    metadata_dict["wavelength_units"] = wavelengthUnits
                except:
                    errors.append("Could not parse wavelength units")

                # Extract band names
                try:
                    bandNames = None
                    if "band_names" in enviData:
                        bandNames = enviData["band_names"].strip("{}").split(",")
                        metadata_dict["band_names"] = bandNames
                except:
                    errors.append("Could not parse band names")

                # Extract wavelengths
                try:
                    wavelengths = None
                    if "wavelength" in enviData:
                        wavelengths = np.asarray(
                            [
                                float(wavelength)
                                for wavelength in enviData["wavelength"]
                                .strip("{}")
                                .split(",")
                            ]
                        )
                        metadata_dict["wavelengths"] = wavelengths
                        metadata_dict["wavelengths_type"] = float
                    elif bandNames is not None:
                        # Try to extract numeric values from band names if they look like wavelengths
                        try:
                            wavelengths = np.asarray(
                                [float(name) for name in bandNames]
                            )
                            metadata_dict["wavelengths"] = wavelengths
                            metadata_dict["wavelengths_type"] = float
                        except ValueError:
                            # Band names don't look like wavelengths, use them as is
                            metadata_dict["wavelengths"] = np.asarray(
                                bandNames, dtype="S"
                            )
                            metadata_dict["wavelengths_type"] = str
                    else:
                        # If all else fails, use band indices
                        bandCount = metadata_dict["bandCount"]
                        metadata_dict["wavelengths"] = np.arange(bandCount)
                        metadata_dict["wavelengths_type"] = int
                        errors.append(
                            "No wavelength information found, using band indices"
                        )
                except Exception as e:
                    # Last resort fallback for wavelengths
                    bandCount = metadata_dict["bandCount"]
                    metadata_dict["wavelengths"] = np.arange(bandCount)
                    metadata_dict["wavelengths_type"] = int
                    errors.append(
                        f"Error extracting wavelengths: {e}, using band indices"
                    )

                # Add extra metadata fields
                extraMetadata = {}
                for key, value in enviData.items():
                    if key not in [
                        "description",
                        "default_bands",
                        "wavelength_units",
                        "band_names",
                        "wavelength",
                        "geospatial_info",
                    ]:
                        extraMetadata[key] = value

                if errors:
                    extraMetadata["loadErrors"] = errors

                metadata_dict["extraMetadata"] = extraMetadata

        except Exception as e:
            logger.error(f"Error opening file for metadata extraction: {e}")
            raise ValueError(f"Failed to extract metadata: {e}")

        try:
            return Metadata(**metadata_dict)
        except Exception as e:
            logger.error(f"Error creating Metadata object: {e}")
            raise ValueError(f"Could not create metadata object: {e}")
