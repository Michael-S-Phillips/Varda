"""Re-binning on zoom must never itself move the view: with X auto-range on,
each re-bin re-padded the range around the new bins and the histogram zoomed
out forever, locking the application."""

import numpy as np
import pytest

from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.image_rendering.image_renderer import ImageRenderer
from varda.image_rendering.new_histogram_view import NewHistogramView


@pytest.fixture
def view(qtbot):
    cube = 0.5 + 0.05 * np.random.default_rng(0).normal(size=(40, 40, 3))
    view = NewHistogramView(ImageRenderer(image=VardaRaster(ArrayDataSource(cube))))
    qtbot.addWidget(view)
    view.resize(500, 300)
    view.show()
    qtbot.waitExposed(view)
    qtbot.wait(50)
    return view


def test_x_auto_range_is_off_once_the_histogram_is_drawn(view):
    viewBox = view.monoPlot.getViewBox()
    xAuto, yAuto = viewBox.autoRangeEnabled()
    assert not xAuto
    assert yAuto


def test_the_x_range_stays_put_while_the_view_repaints(view, qtbot):
    viewBox = view.monoPlot.getViewBox()
    before = viewBox.viewRange()[0]
    changes = []
    viewBox.sigXRangeChanged.connect(lambda *_: changes.append(1))

    for _ in range(5):
        view.monoPlot.repaint()
        viewBox.updateAutoRange()
        qtbot.wait(20)

    assert viewBox.viewRange()[0] == before
    assert changes == []


def test_a_user_zoom_is_honoured_exactly(view, qtbot):
    viewBox = view.monoPlot.getViewBox()
    viewBox.setXRange(0.45, 0.55, padding=0)
    qtbot.wait(50)
    view.monoPlot.repaint()
    qtbot.wait(50)

    assert viewBox.viewRange()[0] == pytest.approx([0.45, 0.55])
