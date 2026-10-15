"""The large view follows the overview's region box exactly, including its
last change (not one change behind)."""

import numpy as np

from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.image_rendering.image_renderer import ImageRenderer, StretchSource
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


def test_the_views_tell_the_renderer_what_they_show_without_a_feedback_loop(qtbot):
    rows, cols = 80, 120
    data = np.random.default_rng(0).random((rows, cols, 3)).astype(np.float32)
    renderer = ImageRenderer(image=VardaRaster(ArrayDataSource(data)))
    view = TripleRasterView(renderer)
    qtbot.addWidget(view)
    view.resize(1200, 700)
    view.show()
    view.roi1.setPos((30, 20))
    view.roi1.setSize((40, 30))
    view.pushStretchWindows()
    main, zoom = (
        renderer._windows[s] for s in (StretchSource.MAIN, StretchSource.ZOOM)
    )
    assert (main[0].start, main[0].stop, main[1].start, main[1].stop) == (
        20,
        50,
        30,
        70,
    )
    assert main[0].start <= zoom[0].start and zoom[0].stop <= main[0].stop
    assert main[1].start <= zoom[1].start and zoom[1].stop <= main[1].stop
    refreshes = []
    renderer.sigShouldRefresh.connect(lambda: refreshes.append(1))
    renderer.settings.stretchFrom.set(StretchSource.ZOOM)
    qtbot.wait(800)  # rendering again must not move the views' windows
    assert len(refreshes) <= 2
