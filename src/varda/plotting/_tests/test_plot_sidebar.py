"""Layout and behaviour of the spectral plot's settings sidebar."""

import numpy as np
from PyQt6.QtWidgets import QLabel

from varda.common.ui import SectionBox
from varda.common.vec2 import Vec2
from varda.plotting.pixel_spectra_plot import PixelSpectraPlotWidget
from varda.plotting.plot import RangeMode, VardaPlotWidget


def _sectionTitles(widget: VardaPlotWidget) -> list[str]:
    layout = widget._sidebar
    sections = (layout.itemAt(i).widget() for i in range(layout.count()))
    return [s.title for s in sections if isinstance(s, SectionBox)]


def _placeholder(widget: VardaPlotWidget) -> QLabel | None:
    for label in widget.curveSettingsBox.frame.findChildren(QLabel):
        if "Click a curve" in label.text():
            return label
    return None


def test_sidebar_leads_with_view_and_ends_with_appearance(qtbot):
    widget = VardaPlotWidget()
    qtbot.addWidget(widget)
    assert _sectionTitles(widget) == [
        "View",
        "Library Spectra",
        "Selected Curve",
        "Appearance",
    ]


def test_pixel_plot_sections_follow_the_view_section(qtbot):
    widget = PixelSpectraPlotWidget()
    qtbot.addWidget(widget)
    assert _sectionTitles(widget)[:2] == ["View", "Pixel Spectra"]


def test_selected_curve_section_shows_placeholder_until_a_curve_is_selected(qtbot):
    widget = VardaPlotWidget()
    qtbot.addWidget(widget)
    curve = widget.plot(np.arange(10.0), np.linspace(0.0, 1.0, 10), name="c")
    assert _placeholder(widget) is not None

    widget.selectPlot(curve)
    assert _placeholder(widget) is None

    widget.deselectPlot()
    assert _placeholder(widget) is not None


def test_fit_to_data_frames_the_curves_and_leaves_auto_range_off(qtbot):
    widget = VardaPlotWidget()
    qtbot.addWidget(widget)
    widget.plot(np.arange(10.0), np.linspace(0.0, 1.0, 10), name="c")
    widget.viewConfig.rangeMode.set(RangeMode.MANUAL)
    widget.rangeConfig.viewRangeX.set(Vec2(4.0, 5.0))
    widget.rangeConfig.viewRangeY.set(Vec2(0.4, 0.5))

    widget.fitToData()

    (xMin, xMax), (yMin, yMax) = widget.viewBox.viewRange()
    assert xMin <= 0.0 and xMax >= 9.0
    assert yMin <= 0.0 and yMax >= 1.0
    assert widget.viewConfig.rangeMode.value is RangeMode.MANUAL
    # manual range boxes reflect the fitted view
    assert widget.rangeConfig.viewRangeX.value.x <= 0.0
