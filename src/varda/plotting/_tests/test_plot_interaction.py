"""Mouse interaction and control granularity of the spectral plot."""

import pyqtgraph as pg
from PyQt6.QtCore import Qt

from varda.plotting.plot import CurveConfig, RangeConfig, VardaPlotWidget
from varda.plotting.view_box import dragMouseMode

Modifier = Qt.KeyboardModifier


def test_plain_drag_pans_while_modified_drag_zooms_to_box():
    assert dragMouseMode(Modifier.NoModifier) == pg.ViewBox.PanMode
    for modifier in (
        Modifier.ShiftModifier,
        Modifier.ControlModifier,
        Modifier.MetaModifier,
    ):
        assert dragMouseMode(modifier) == pg.ViewBox.RectMode


def test_plot_starts_in_pan_mode_with_gentler_wheel_zoom_than_default(qtbot):
    widget = VardaPlotWidget()
    qtbot.addWidget(widget)
    assert widget.viewBox.state["mouseMode"] == pg.ViewBox.PanMode
    # pyqtgraph's default of 1/8 zooms ~26% per wheel notch
    assert abs(widget.viewBox.state["wheelScaleFactor"]) < 1.0 / 8.0


def test_curve_scale_cannot_reach_zero_and_steps_finely():
    config = CurveConfig()
    assert config.scale.range is not None and config.scale.range[0] > 0
    assert config.scale.step is not None and config.scale.step <= 0.1
    assert config.offset.step is not None and config.offset.step <= 0.01


def test_y_view_range_steps_finely_for_reflectance():
    config = RangeConfig()
    assert config.viewRangeY.step is not None and config.viewRangeY.step <= 0.01
