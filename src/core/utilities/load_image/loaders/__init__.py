from os import listdir
from os.path import dirname, basename
from .enviimageloader import ENVIImageLoader
from .hdf5imageloader import HDF5ImageLoader
from .abstractimageloader import AbstractImageLoader

# This dynamically imports all the modules in this package. ty StackOverflow
__all__ = [
    basename(f)[:-3]
    for f in listdir(dirname(__file__))
    if f[-3:] == ".py"
    and not f.endswith("__init__.py")
    and not f.endswith("abstractimageloader.py")
]

print("imageloaders __init__.py: ", __all__)
