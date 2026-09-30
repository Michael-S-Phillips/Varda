"""Every plotted pixel spectrum is marked on the image(s) it came from, in the
curve's colour, for as long as the curve is on a plot."""

import numpy as np
import PyQt6Ads as ads
import pytest
from psygnal import Signal
from PyQt6.QtCore import QPointF
from PyQt6.QtWidgets import QLabel, QMainWindow

from varda.common.ui import VardaDockWidget
from varda.plotting.pixel_spectra_plot import SpectrumMode
from varda.utilities.debug import generate_random_image
from varda.workspaces.pixel_markers import PixelMarkerController
from varda.workspaces.pixel_spectra_docks import PixelSpectraDocks


class FakeMarker:
    def __init__(self, pos: QPointF, color) -> None:
        self.pos = pos
        self.color = color
        self.removed = False

    def setPos(self, pos: QPointF) -> None:
        self.pos = pos

    def setColor(self, color) -> None:
        self.color = color

    def setVisible(self, visible: bool) -> None:
        pass

    def remove(self) -> None:
        self.removed = True


class FakeViewport:
    sigImageChanged = Signal()  # fires when the shown region (local coords) moves

    def __init__(self) -> None:
        self.markers: list[FakeMarker] = []
        # a viewport showing a region of the image has shifted local coordinates
        self.offset = np.array([0.0, 0.0])

    def pixelToLocalCoords(self, pixelCoords: np.ndarray) -> np.ndarray:
        return np.asarray(pixelCoords, dtype=float) - self.offset

    def addPointOverlay(self, pos: QPointF, color) -> FakeMarker:
        marker = FakeMarker(pos, color)
        self.markers.append(marker)
        return marker

    def live(self) -> list[FakeMarker]:
        return [m for m in self.markers if not m.removed]


@pytest.fixture
def setup(qtbot):
    window = QMainWindow()
    qtbot.addWidget(window)
    manager = ads.CDockManager(window)
    anchor = VardaDockWidget("ROI Plots")
    anchor.setWidget(QLabel("anchor"))
    manager.addDockWidget(ads.DockWidgetArea.BottomDockWidgetArea, anchor)
    docks = PixelSpectraDocks(manager, anchor, parent=window)
    viewports = [FakeViewport(), FakeViewport()]
    controller = PixelMarkerController(docks, viewports, parent=window)
    image = generate_random_image((20, 20, 10))
    yield docks, viewports, controller, image
    del window


def test_a_plotted_pixel_is_marked_at_its_centre_on_every_viewport(setup):
    docks, viewports, _c, image = setup

    (curve,) = docks.addPixelSpectra([image], 3, 5)

    for viewport in viewports:
        (marker,) = viewport.live()
        assert (marker.pos.x(), marker.pos.y()) == (3.5, 5.5)
        assert marker.color == curve.config.color.value


def test_collect_mode_keeps_a_marker_per_spectrum_and_replace_keeps_the_latest(setup):
    docks, viewports, _c, image = setup
    plot = docks.active
    plot.pixelConfig.mode.set(SpectrumMode.COLLECT)
    docks.addPixelSpectra([image], 3, 5)
    docks.addPixelSpectra([image], 7, 9)
    assert len(viewports[0].live()) == 2

    plot.pixelConfig.mode.set(SpectrumMode.REPLACE)
    docks.addPixelSpectra([image], 1, 1)

    (marker,) = viewports[0].live()
    assert (marker.pos.x(), marker.pos.y()) == (1.5, 1.5)


def test_markers_go_when_their_curves_go(setup):
    docks, viewports, _c, image = setup
    plot = docks.active
    (first,) = docks.addPixelSpectra([image], 3, 5)
    docks.addPixelSpectra([image], 7, 9)

    plot.removePlot(first)
    assert len(viewports[0].live()) == 1

    plot.clearPixelSpectra()
    assert viewports[0].live() == []


def test_markers_follow_a_viewport_whose_shown_region_moves(setup):
    docks, viewports, _c, image = setup
    docks.addPixelSpectra([image], 3, 5)
    panned = viewports[1]

    panned.offset = np.array([2.0, 1.0])  # the region view panned by (2, 1)
    panned.sigImageChanged.emit()

    (marker,) = panned.live()
    assert (marker.pos.x(), marker.pos.y()) == (1.5, 4.5)
    (other,) = viewports[0].live()
    assert (other.pos.x(), other.pos.y()) == (3.5, 5.5)  # untouched view


def test_spectra_on_a_plot_opened_later_are_marked_too(setup):
    docks, viewports, _c, image = setup
    docks.addPixelSpectra([image], 3, 5)
    docks.newPlot()

    docks.addPixelSpectra([image], 7, 9)

    assert len(viewports[0].live()) == 2
