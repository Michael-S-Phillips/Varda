"""The large view follows the overview's region box exactly, including its
last change (not one change behind)."""

import numpy as np

from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.image_rendering.image_renderer import ImageRenderer
from varda.image_rendering.raster_view.triple_raster_view import TripleRasterView


def test_the_large_view_shows_the_region_just_set(qtbot):
    rows, cols = 80, 120
    data = np.random.default_rng(0).random((rows, cols, 3)).astype(np.float32)
    view = TripleRasterView(ImageRenderer(image=VardaRaster(ArrayDataSource(data))))
    qtbot.addWidget(view)
    view.resize(1200, 700)
    view.show()
    view.roi1.setPos((0, 0))
    view.roi1.setSize((cols, rows))
    shown = view.viewport2._imageItem.image
    assert shown is not None and shown.shape[:2] == (rows, cols)
