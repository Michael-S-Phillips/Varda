# Import data_sources to trigger decorator-based registration
from .data_source import DataSource
from .array_data_source import ArrayDataSource
from .rasterio_data_source import RasterioDataSource
from .envi_data_source import ENVIDataSource
from .crism_data_source import CrismMapLabelDataSource, CrismProductDataSource
from .hdf5_data_source import HDF5DataSource
from .in_memory_data_source import InMemoryDataSource

__all__ = [
    "DataSource",
    "ArrayDataSource",
    "RasterioDataSource",
    "ENVIDataSource",
    "CrismMapLabelDataSource",
    "CrismProductDataSource",
    "HDF5DataSource",
    "InMemoryDataSource",
]
