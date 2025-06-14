# varda/core/utilities/load_image/loaders/__init__.py
from .abstractimageloader import AbstractImageLoader, LOADER_REGISTRY

# Importing all loader implementations so they register themselves
from .enviimageloader import ENVIImageLoader
from .tiffimageloader import TIFFImageLoader
from .hdf5imageloader import HDF5ImageLoader
from .pillowimageloader import PillowImageLoader

# Re-export the get_loader_for_file function
from .abstractimageloader import AbstractImageLoader as _AbstractImageLoader

# Export key names
__all__ = [
    "AbstractImageLoader",
    "ENVIImageLoader",
    "TIFFImageLoader",
    "HDF5ImageLoader",
    "PillowImageLoader",
    "LOADER_REGISTRY",
]
