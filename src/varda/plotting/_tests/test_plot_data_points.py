"""Spectral plots can mark the wavelengths that carry measured channel data,
so a user can tell real samples from the straight lines drawn between them."""

import numpy as np
import pyqtgraph as pg
import pytest
from PyQt6.QtGui import QColor

from varda.plotting.plot import VardaPlotWidget


@pytest.fixture
def widget(qtbot):
    widget = VardaPlotWidget()
    qtbot.addWidget(widget)
    return widget


def _symbol(curve):
    return curve.plotDataItem.opts["symbol"]


def _symbolBrushColor(curve) -> QColor:
    return pg.mkBrush(curve.plotDataItem.opts["symbolBrush"]).color()


def test_curves_are_plain_lines_by_default(widget):
    curve = widget.plot([1.0, 2.0, 3.0], [0.1, 0.2, 0.3])
    assert not widget.viewConfig.showDataPoints.value
    assert _symbol(curve) is None


def test_show_data_points_marks_every_sample_on_existing_and_new_curves(widget):
    existing = widget.plot([1.0, 2.0, 3.0], [0.1, 0.2, 0.3])

    widget.viewConfig.showDataPoints.set(True)
    added = widget.plot([1.0, 2.0, 3.0], [0.3, 0.2, 0.1])

    assert _symbol(existing) == "o" and _symbol(added) == "o"
    widget.viewConfig.showDataPoints.set(False)
    assert _symbol(existing) is None and _symbol(added) is None


def test_data_points_take_the_curve_colour_and_follow_colour_changes(widget):
    widget.viewConfig.showDataPoints.set(True)
    curve = widget.plot([1.0, 2.0], [0.1, 0.2])
    curve.config.color.set(QColor("#00ff00"))

    assert _symbolBrushColor(curve).name() == "#00ff00"


def test_data_point_size_is_adjustable(widget):
    widget.viewConfig.showDataPoints.set(True)
    curve = widget.plot([1.0, 2.0], [0.1, 0.2])

    widget.viewConfig.dataPointSize.set(9)

    assert curve.plotDataItem.opts["symbolSize"] == 9


def test_fill_band_edges_never_get_data_points(widget):
    widget.viewConfig.showDataPoints.set(True)
    x = np.array([1.0, 2.0, 3.0])
    curve = widget.plotWithFill(x, x * 0.1, x * 0.05, x * 0.15, pg.mkBrush("#80808080"))

    assert _symbol(curve) == "o"
    assert all(item.opts["symbol"] is None for item in curve.bandItems[:2])
