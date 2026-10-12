import os
import sys

# Use the PROJ/GDAL data bundled with this environment's rasterio and pyproj.
# A shell with another installation active (e.g. conda base) exports its own
# PROJ_DATA/GDAL_DATA; PROJ then reads a proj.db of the wrong version, fails to
# create CRSs, and has crashed Varda. Done here, before rasterio/pyproj load.
for _var in ("PROJ_DATA", "PROJ_LIB", "GDAL_DATA"):
    _path = os.environ.get(_var)
    if _path and not os.path.realpath(_path).startswith(os.path.realpath(sys.prefix)):
        del os.environ[_var]

from . import log as log  # noqa: E402
from . import utilities as utilities  # noqa: E402
