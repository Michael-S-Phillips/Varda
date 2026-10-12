"""One lock for every use of PROJ (pyproj) across threads.

PROJ is not thread-safe: creating a CRS in an analysis worker while the GUI
thread transforms coordinates (the pixel readout) crashed Varda with a SIGSEGV
in proj_create. Hold PROJ_LOCK around CRS construction, transformer creation,
transforms and WKT export.
"""

import threading

PROJ_LOCK = threading.RLock()
