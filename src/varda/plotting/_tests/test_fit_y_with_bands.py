"""Fit Y To X Range fits the curves inside the window, shaded bands included."""

import numpy as np
from PyQt6.QtGui import QBrush, QColor

from varda.common.vec2 import Vec2
from varda.plotting.plot import RangeMode, VardaPlotWidget


def test_y_fits_the_window_when_curves_have_std_bands(qtbot):
    plot = VardaPlotWidget()
    qtbot.addWidget(plot)
    plot.resize(600, 400)
    plot.show()
    x = np.linspace(0, 100, 201)
    y = np.where(x < 50, 0.5, 10.0)  # the right half is far higher
    plot.plotWithFill(x, y, y - 0.1, y + 0.1, fillBrush=QBrush(QColor(255, 0, 0, 60)))
    plot.viewConfig.rangeMode.set(RangeMode.FIT_Y_TO_X_RANGE)
    plot.rangeConfig.viewRangeX.set(Vec2(0.0, 40.0))
    qtbot.waitUntil(lambda: plot.viewBox.viewRange()[1][1] < 2.0, timeout=2000)
    low, high = plot.viewBox.viewRange()[1]
    assert low < 0.4 and high > 0.6  # the band around 0.5 fits inside
