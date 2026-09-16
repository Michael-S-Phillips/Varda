"""Range modes (Auto / Fit Y to X range / Manual) and the legend toggle."""

import numpy as np
import pytest

from varda.common.vec2 import Vec2
from varda.plotting.plot import RangeMode, VardaPlotWidget


@pytest.fixture
def widget(qtbot):
    widget = VardaPlotWidget()
    qtbot.addWidget(widget)
    return widget


def _settle(qtbot, widget: VardaPlotWidget) -> None:
    """Let Qt paint the plot: pyqtgraph syncs the view range and re-runs
    auto-range during paint, which an unpainted test widget never does."""
    widget.show()
    qtbot.waitExposed(widget)
    qtbot.wait(20)
    widget.viewBox.updateAutoRange()


def _spiky(level: float) -> tuple[np.ndarray, np.ndarray]:
    """Gently varying around ``level`` inside x 40..60, spikes to 10 outside it.

    (Not perfectly flat inside: pyqtgraph ignores a zero-height auto-range.)
    """
    x = np.arange(100.0)
    y = np.where((x >= 40) & (x <= 60), level + 0.05 * np.sin(x), 10.0)
    return x, y


def test_legend_can_be_hidden_and_shown(widget):
    widget.plot(np.arange(5.0), np.arange(5.0), name="c")
    assert widget.plotItem.legend.isVisible()

    widget.viewConfig.showLegend.set(False)
    assert not widget.plotItem.legend.isVisible()

    widget.viewConfig.showLegend.set(True)
    assert widget.plotItem.legend.isVisible()


def test_fit_y_to_x_range_fits_y_to_the_data_inside_the_x_window(qtbot, widget):
    widget.plot(*_spiky(0.3), name="c")
    widget.viewConfig.rangeMode.set(RangeMode.FIT_Y_TO_X_RANGE)
    widget.rangeConfig.viewRangeX.set(Vec2(40.0, 60.0))
    _settle(qtbot, widget)

    (xMin, xMax), (yMin, yMax) = widget.viewBox.viewRange()
    assert (xMin, xMax) == pytest.approx((40.0, 60.0))
    assert yMax < 1.0  # the spikes to 10 outside the window are ignored
    assert yMin <= 0.3 <= yMax


def test_fit_y_to_x_range_refits_when_a_spectrum_arrives(qtbot, widget):
    widget.plot(*_spiky(0.3), name="first")
    widget.viewConfig.rangeMode.set(RangeMode.FIT_Y_TO_X_RANGE)
    widget.rangeConfig.viewRangeX.set(Vec2(40.0, 60.0))
    _settle(qtbot, widget)

    widget.plot(*_spiky(0.8), name="second")
    _settle(qtbot, widget)

    (xMin, xMax), (_yMin, yMax) = widget.viewBox.viewRange()
    assert (xMin, xMax) == pytest.approx((40.0, 60.0))  # X window kept
    assert 0.8 <= yMax < 1.0  # Y grew to show the new spectrum, still ignoring spikes


def test_user_pan_in_fit_y_mode_keeps_the_mode_and_y_auto(widget):
    widget.plot(*_spiky(0.3), name="c")
    widget.viewConfig.rangeMode.set(RangeMode.FIT_Y_TO_X_RANGE)
    widget.rangeConfig.viewRangeX.set(Vec2(40.0, 60.0))

    widget.viewBox.setXRange(45.0, 55.0, padding=0)  # as a drag would
    widget._onUserViewChange()

    assert widget.viewConfig.rangeMode.value is RangeMode.FIT_Y_TO_X_RANGE
    assert widget.rangeConfig.viewRangeX.value.x == pytest.approx(45.0)
    assert widget.viewBox.state["autoRange"][1]  # Y still automatic


def test_user_pan_in_auto_mode_switches_to_manual(widget):
    widget.plot(*_spiky(0.3), name="c")
    widget.viewBox.setXRange(45.0, 55.0, padding=0)
    widget._onUserViewChange()
    assert widget.viewConfig.rangeMode.value is RangeMode.MANUAL
