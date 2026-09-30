"""A curve plotted with a +/- band owns that band: it moves and goes with the curve."""

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import QPointF

from varda.plotting.plot import VardaPlotWidget

X = np.arange(10.0)
MEAN = np.linspace(0.2, 0.6, 10)
STD = np.full(10, 0.05)


def _plotWithBand(qtbot):
    widget = VardaPlotWidget()
    qtbot.addWidget(widget)
    curve = widget.plotWithFill(
        X,
        MEAN,
        yLower=MEAN - STD,
        yUpper=MEAN + STD,
        fillBrush=pg.mkBrush("r"),
        name="roi",
    )
    return widget, curve


def _bandItems(widget: VardaPlotWidget):
    return [i for i in widget.plotItem.items if isinstance(i, pg.FillBetweenItem)]


def test_removing_a_curve_removes_its_band(qtbot):
    widget, curve = _plotWithBand(qtbot)
    assert len(_bandItems(widget)) == 1

    widget.removePlot(curve)

    assert _bandItems(widget) == []
    assert widget.plotItem.listDataItems() == []


def test_clearing_plots_removes_bands(qtbot):
    widget, _curve = _plotWithBand(qtbot)
    widget.clearPlots()
    assert _bandItems(widget) == []
    assert widget.plotItem.listDataItems() == []


def test_band_follows_the_curves_offset_and_scale(qtbot):
    _widget, curve = _plotWithBand(qtbot)
    curve.config.scale.set(2.0)
    curve.config.offset.set(10.0)

    expected = curve.plotDataItem.transform().map(QPointF(0.0, 1.0)).y()
    assert expected == 12.0
    assert curve.bandItems  # the band is attached to the curve
    for item in curve.bandItems:
        assert item.transform().map(QPointF(0.0, 1.0)).y() == expected
