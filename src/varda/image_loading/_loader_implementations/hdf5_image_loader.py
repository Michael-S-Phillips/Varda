"""
HDF5 Image Loader implementation.
"""

# standard library
import time
import logging

# third party imports
import h5py
import numpy as np
import rasterio as rio

# local imports
from varda.common.entities import Metadata
from varda.common.entities import Band
from varda.image_loading import registerImageLoader
from varda.image_loading import ImageLoaderProtocol
from varda.utilities import debug

logger = logging.getLogger(__name__)


@registerImageLoader("HDF5 Image", (".h5", ".hdf5"))
class HDF5ImageLoader(ImageLoaderProtocol):
    """Implementation of ImageLoader for HDF5 Images"""

    @staticmethod
    def loadRasterData(filePath, loading_mode="full") -> np.ndarray:
        """Load raster data from HDF5 file.

        Args:
            filePath: Path to the HDF5 file
            loading_mode: 'full', 'preview', or 'metadata'

        Returns:
            np.ndarray: The raster data
        """
        timeStarted = time.time()
        # try:
        #     with rio.open(filePath) as src:
        #         try:
        #             data = src.read()
        #         except Exception as e:
        #             logger.error(
        #                 f"Error reading raster data using rasterio from {filePath}: {e}"
        #             )
        # except Exception as e:
        #     logger.error(f"Error opening raster file using rasterio for reading: {e}")

        try:
            with h5py.File(filePath, "r") as hdf:
                if debug.DEBUG:
                    logger.debug("Time to open file: %s", time.time() - timeStarted)
                    logger.debug("Available groups/datasets in the file:")

                    def print_attrs(name, obj):
                        logger.debug(f"{name}: {obj}")
                        return None

                    hdf.visititems(print_attrs)

                # Find the dataset containing the actual raster data
                # Strategy 1: Try to follow a known structure
                dataset = None
                known_paths = [
                    "SERC/Reflectance/Reflectance_Data",
                    "Reflectance/Reflectance_Data",
                    "Reflectance_Data",
                    "Data/Reflectance",
                    "Data",
                ]

                for path in known_paths:
                    try:
                        dataset = hdf[path]
                        logger.info(f"Found dataset at {path}")
                        break
                    except (KeyError, AttributeError):
                        pass

                # Strategy 2: Navigate through the hierarchy to find a suitable dataset
                if dataset is None:
                    logger.info("Looking for dataset in HDF5 hierarchy")
                    f = hdf
                    visited = set()
                    queue = [f]

                    while queue and dataset is None:
                        current = queue.pop(0)

                        # Skip if already visited to avoid circular references
                        if id(current) in visited:
                            continue
                        visited.add(id(current))

                        # Check if this is a dataset with a suitable shape
                        if (
                            isinstance(current, h5py.Dataset)
                            and len(current.shape) >= 2
                        ):
                            if len(current.shape) == 3 or (
                                len(current.shape) == 2
                                and current.shape[0] > 1
                                and current.shape[1] > 1
                            ):
                                dataset = current
                                logger.info(f"Found dataset at {current.name}")
                                break

                        # If it's a group, add its children to the queue
                        if isinstance(current, h5py.Group):
                            for key in current:
                                queue.append(current[key])

                if dataset is None:
                    raise ValueError(
                        "Could not find a suitable dataset in the HDF5 file"
                    )

                # Check if we're in preview mode for large datasets
                if loading_mode == "preview" and dataset is not None:
                    # Calculate dimensions for preview
                    preview_scale = 8  # Adjust based on your needs

                    # If dataset shape is (bands, height, width)
                    if len(dataset.shape) == 3:
                        out_shape = (
                            dataset.shape[0],
                            dataset.shape[1] // preview_scale,
                            dataset.shape[2] // preview_scale,
                        )
                        data = dataset[
                            :,  # All bands
                            ::preview_scale,  # Stride by preview_scale in height
                            ::preview_scale,  # Stride by preview_scale in width
                        ]
                    # If dataset shape is (height, width, bands)
                    elif len(dataset.shape) == 3:
                        data = dataset[
                            ::preview_scale,  # Stride by preview_scale in height
                            ::preview_scale,  # Stride by preview_scale in width
                            :,  # All bands
                        ]
                    else:
                        # For other shapes, load full data
                        data = dataset[:]

                    logger.info(f"Loaded preview with scale factor {preview_scale}")
                else:
                    # Full resolution data
                    timeStarted = time.time()
                    data = dataset[:]
                    logger.debug(f"Time to read data: {time.time() - timeStarted}")

                # Ensure the data has 3 dimensions (height, width, bands)
                if len(data.shape) == 2:
                    data = data.reshape(data.shape[0], data.shape[1], 1)
                elif len(data.shape) > 3:
                    # Handle case with more than 3 dimensions
                    # For example, some files might have (time, height, width, bands)
                    # Take the first time slice for now
                    data = (
                        data[0]
                        if data.shape[0] == 1
                        else data.reshape(-1, data.shape[-2], data.shape[-1])
                    )

                # Ensure the dimensions are in the correct order (height, width, bands)
                # Check if bands are in the first dimension
                if data.shape[0] < data.shape[1] and data.shape[0] < data.shape[2]:
                    # Transpose from (bands, height, width) to (height, width, bands)
                    data = np.transpose(data, (1, 2, 0))

                return data

        except Exception as e:
            logger.error(f"Failed to load raster data from HDF5 file: {e}")
            raise ValueError(f"Could not read HDF5 file: {e}")

    @staticmethod
    def loadMetadata(raster, filePath) -> Metadata:
        metadata_dict = {}
        errors = []

        try:
            with h5py.File(filePath, "r") as hdf:
                # Basic metadata that we can derive from the raster
                metadata_dict["filePath"] = filePath
                metadata_dict["driver"] = "HDF5"
                metadata_dict["width"] = raster.shape[1]
                metadata_dict["height"] = raster.shape[0]
                metadata_dict["dtype"] = str(raster.dtype)
                metadata_dict["bandCount"] = raster.shape[2]

                # Try to find wavelength information
                wavelengths = None

                # Strategy 1: Look for wavelengths in known locations
                wavelength_paths = [
                    "SERC/Reflectance/Metadata/Spectral_Data/Wavelength",
                    "Reflectance/Metadata/Spectral_Data/Wavelength",
                    "Metadata/Spectral_Data/Wavelength",
                    "Wavelength",
                ]

                for path in wavelength_paths:
                    try:
                        wavelengths = hdf[path][:]
                        logger.info(f"Found wavelength data at {path}")
                        break
                    except (KeyError, AttributeError):
                        pass

                # Strategy 2: Search for datasets containing "wavelength" in their name
                if wavelengths is None:
                    logger.info("Searching for wavelength data in HDF5 hierarchy")

                    def find_wavelength(name, obj):
                        nonlocal wavelengths
                        if wavelengths is not None:
                            return

                        if isinstance(obj, h5py.Dataset):
                            if "wavelength" in name.lower() and len(obj.shape) <= 2:
                                try:
                                    wavelengths = obj[:]
                                    logger.info(f"Found wavelength data at {name}")
                                except Exception as e:
                                    logger.debug(
                                        f"Error reading wavelength data from {name}: {e}"
                                    )

                    hdf.visititems(find_wavelength)

                # Set wavelengths or create defaults
                if wavelengths is not None:
                    # Ensure wavelengths is a 1D array
                    if len(wavelengths.shape) > 1:
                        wavelengths = wavelengths.flatten()

                    if len(wavelengths) == raster.shape[2]:
                        metadata_dict["wavelengths"] = wavelengths
                        metadata_dict["wavelengths_type"] = float
                    else:
                        logger.warning(
                            "Wavelength count doesn't match band count, using band indices"
                        )
                        metadata_dict["wavelengths"] = np.arange(raster.shape[2])
                        metadata_dict["wavelengths_type"] = int
                        errors.append("Wavelength count mismatch")
                else:
                    logger.warning(
                        "No wavelength information found, using band indices"
                    )
                    metadata_dict["wavelengths"] = np.arange(raster.shape[2])
                    metadata_dict["wavelengths_type"] = int
                    errors.append("No wavelength information found")

                # Create a default band if we have at least 3 bands
                if raster.shape[2] >= 3:
                    metadata_dict["defaultBand"] = Band("default", 0, 1, 2)
                else:
                    metadata_dict["defaultBand"] = Band("default", 0, 0, 0)

                # Add any other metadata that might be useful
                extraMetadata = {}

                # Look for metadata about the dataset
                for path in ["Metadata", "SERC/Reflectance/Metadata"]:
                    try:
                        metadata_group = hdf[path]
                        for key in metadata_group.keys():
                            try:
                                value = metadata_group[key][()]
                                if isinstance(value, np.ndarray) and value.size == 1:
                                    value = value.item()
                                extraMetadata[key] = str(value)
                            except Exception as e:
                                logger.debug(f"Could not read metadata {key}: {e}")
                    except (KeyError, AttributeError):
                        pass

                # Store file attributes
                try:
                    for key, value in hdf.attrs.items():
                        if isinstance(value, np.ndarray) and value.size == 1:
                            value = value.item()
                        extraMetadata[f"file_attr_{key}"] = str(value)
                except Exception as e:
                    logger.debug(f"Could not read file attributes: {e}")

                if errors:
                    extraMetadata["loadErrors"] = errors

                metadata_dict["extraMetadata"] = extraMetadata

        except Exception as e:
            logger.error(f"Error opening HDF5 file for metadata extraction: {e}")
            raise ValueError(f"Failed to extract metadata from HDF5 file: {e}")

        try:
            return Metadata(**metadata_dict)
        except Exception as e:
            logger.error(f"Error creating Metadata object: {e}")
            raise ValueError(f"Could not create metadata object: {e}")
