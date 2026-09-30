"""Zooming a display histogram re-bins it over the visible range and refits Y,
so a peak of valid values is not dwarfed by a stack of fill values in the tail."""

import numpy as np
import pytest

from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.image_rendering.image_renderer import ImageRenderer
from varda.image_rendering.new_histogram_view import NewHistogramView


@pytest.fixture
def view(qtbot):
    rng = np.random.default_rng(0)
    # 60% of the pixels are a fill value far out in the tail, the rest a
    # gentle distribution of valid values around 0.5.
    cube = 0.5 + 0.05 * rng.normal(size=(50, 50, 3))
    cube[:30, :, :] = -9999.0
    image = VardaRaster(ArrayDataSource(cube), name="params")
    view = NewHistogramView(ImageRenderer(image=image))
    qtbot.addWidget(view)
    view.resize(500, 300)
    view.show()
    qtbot.waitExposed(view)
    qtbot.wait(50)
    return view


def _curve(plot):
    (item,) = [i for i in plot.listDataItems()]
    return item.getData()


def test_zooming_in_rebins_over_the_visible_range_and_refits_y(view, qtbot):
    plot = view.monoPlot  # the renderer starts in mono mode
    viewBox = plot.getViewBox()
    _, yBefore = _curve(plot)
    yMaxBefore = viewBox.viewRange()[1][1]
    assert yBefore.max() >= 0.6 * 2500  # the fill-value stack dominates

    viewBox.setXRange(0.3, 0.7, padding=0)
    qtbot.wait(50)

    x, y = _curve(plot)
    assert x.min() >= 0.3 and x.max() <= 0.7  # binned over what is visible
    assert len(x) >= 100  # at full resolution, not one bar
    assert y.max() < 0.6 * 2500  # the stack is out of view...
    assert viewBox.viewRange()[1][1] < yMaxBefore / 2  # ...and Y follows


def test_histogram_x_axis_can_be_zoomed_with_the_mouse(view):
    for plot in (view.monoPlot, view.rPlot, view.gPlot, view.bPlot):
        assert plot.getViewBox().state["mouseEnabled"] == [True, False]
