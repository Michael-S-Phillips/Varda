"""A curve's Y scale/offset must mean the same thing everywhere it is used."""

import numpy as np
from PyQt6.QtCore import QPointF

from varda.plotting.plot import VardaPlotWidget


def test_drawn_position_matches_displayed_data(qtbot):
    widget = VardaPlotWidget()
    qtbot.addWidget(widget)
    y = np.array([1.0, 2.0, 3.0])
    curve = widget.plot(np.arange(3.0), y, name="c")
    curve.config.scale.set(2.0)
    curve.config.offset.set(10.0)

    _x, shown = curve.displayedData()
    drawn = [curve.plotDataItem.transform().map(QPointF(0.0, v)).y() for v in y]

    np.testing.assert_allclose(drawn, shown)
    np.testing.assert_allclose(shown, y * 2.0 + 10.0)


def test_view_limits_contain_where_a_rescaled_curve_is_drawn(qtbot):
    widget = VardaPlotWidget()
    qtbot.addWidget(widget)
    y = np.linspace(100.0, 300.0, 10)
    curve = widget.plot(np.arange(10.0), y, name="c")
    curve.config.scale.set(0.002)
    curve.config.offset.set(-0.15)

    drawn = np.array(
        [curve.plotDataItem.transform().map(QPointF(0.0, v)).y() for v in y]
    )
    yMin, yMax = widget.viewBox.state["limits"]["yLimits"]
    assert yMin <= drawn.min() and yMax >= drawn.max()
