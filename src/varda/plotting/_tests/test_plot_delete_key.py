"""Backspace / Delete removes the selected curve from a plot."""

import numpy as np
import pytest
from PyQt6.QtCore import Qt

from varda.plotting.plot import VardaPlotWidget


@pytest.fixture
def widget(qtbot):
    widget = VardaPlotWidget()
    qtbot.addWidget(widget)
    return widget


def _twoCurves(widget):
    x = np.linspace(1000.0, 2500.0, 16)
    return widget.plot(x, x * 1e-4, name="a"), widget.plot(x, x * 2e-4, name="b")


@pytest.mark.parametrize("key", [Qt.Key.Key_Backspace, Qt.Key.Key_Delete])
def test_backspace_or_delete_removes_the_selected_curve(widget, qtbot, key):
    a, b = _twoCurves(widget)
    widget.selectPlot(a)

    qtbot.keyClick(widget, key)

    assert a not in widget.plots
    assert b in widget.plots
    assert widget.selectedCurve is None


def test_the_keys_do_nothing_without_a_selection(widget, qtbot):
    a, b = _twoCurves(widget)

    qtbot.keyClick(widget, Qt.Key.Key_Backspace)

    assert widget.plots == [a, b]
