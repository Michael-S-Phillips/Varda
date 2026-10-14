"""Images display as stored: rows run down the view, columns across it,
whichever code builds the viewport (not only the app's startup)."""

import numpy as np

from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.image_rendering.image_renderer import ImageRenderer
from varda.image_rendering.raster_view.image_viewport import ImageViewport


def test_a_wide_image_displays_wide_with_its_first_row_on_top(qtbot):
    rows, cols = 10, 30
    data = np.zeros((rows, cols, 1), dtype=np.float32)
    data[0, :, 0] = 1.0  # a bright top row
    image = VardaRaster(ArrayDataSource(data), name="wide")
    viewport = ImageViewport(ImageRenderer(image=image))
    qtbot.addWidget(viewport)
    item = viewport._imageItem
    viewport.refresh()
    assert (item.width(), item.height()) == (cols, rows)  # not transposed
    shown = item.image
    assert shown is not None and shown.shape[:2] == (rows, cols)
