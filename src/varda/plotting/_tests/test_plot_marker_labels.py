"""Marker labels: draggable, hideable, rotatable, and kept from colliding."""

import numpy as np
import pytest

from varda.plotting.plot import VardaPlotWidget


@pytest.fixture
def widget(qtbot):
    widget = VardaPlotWidget()
    qtbot.addWidget(widget)
    widget.resize(700, 400)
    widget.show()
    qtbot.waitExposed(widget)
    widget.plot(np.linspace(1000.0, 2600.0, 161), np.linspace(0.2, 0.6, 161), name="c")
    qtbot.wait(50)
    return widget


def test_marker_labels_are_draggable_along_the_line(widget):
    marker = widget.addMarker(1900.0)
    assert marker.label.movable


def test_labels_of_markers_close_together_are_staggered(widget, qtbot):
    close1 = widget.addMarker(2170.9)
    close2 = widget.addMarker(2205.4)
    far = widget.addMarker(1200.0)
    qtbot.wait(50)

    assert close1.label.orthoPos != close2.label.orthoPos
    assert far.label.orthoPos == close1.label.orthoPos  # nothing to dodge


def test_staggering_follows_a_marker_that_is_dragged_apart(widget, qtbot):
    first = widget.addMarker(2170.9)
    second = widget.addMarker(2205.4)
    qtbot.wait(50)
    assert first.label.orthoPos != second.label.orthoPos

    second.setValue(1400.0)
    qtbot.wait(50)

    assert first.label.orthoPos == second.label.orthoPos


def test_a_label_the_user_dragged_stays_where_it_was_put(widget, qtbot):
    marker = widget.addMarker(2170.9)
    marker.label.userPlaced = True
    marker.label.setPosition(0.3)

    widget.addMarker(2205.4)  # would otherwise re-stagger the first label
    qtbot.wait(50)

    assert marker.label.orthoPos == 0.3


def test_marker_labels_can_be_hidden_and_shown(widget):
    marker = widget.addMarker(1900.0)
    assert marker.label.isVisible()

    widget.markerConfig.showLabels.set(False)
    later = widget.addMarker(2300.0)
    assert not marker.label.isVisible()
    assert not later.label.isVisible()

    widget.markerConfig.showLabels.set(True)
    assert marker.label.isVisible() and later.label.isVisible()


def test_marker_labels_can_be_rotated_vertical(widget):
    marker = widget.addMarker(1900.0)
    assert marker.label.angle == 0

    widget.markerConfig.verticalLabels.set(True)
    later = widget.addMarker(2300.0)
    assert marker.label.angle == 90
    assert later.label.angle == 90

    widget.markerConfig.verticalLabels.set(False)
    assert marker.label.angle == 0
