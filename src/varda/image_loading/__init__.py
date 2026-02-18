from .image_loading_service import ImageLoadingService
from .varda_raster import VardaRaster

# Import data_sources to trigger decorator-based registration
from .data_sources import (
    DataSource,
    ArrayDataSource,
    RasterioDataSource,
    ENVIDataSource,
    HDF5DataSource,
    InMemoryDataSource,
)
