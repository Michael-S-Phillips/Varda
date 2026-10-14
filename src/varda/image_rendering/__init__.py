import pyqtgraph as pg

# Varda's image arrays are (rows, columns, bands). pyqtgraph assumes
# (columns, rows) unless told otherwise, which shows every image transposed
# (rotated and mirrored). Set here, not at app startup, so every viewport,
# test and script that renders images gets it.
pg.setConfigOptions(imageAxisOrder="row-major")

from .image_renderer import ImageRenderer  # noqa: E402
from .raster_view.image_viewport import ImageViewport  # noqa: E402
