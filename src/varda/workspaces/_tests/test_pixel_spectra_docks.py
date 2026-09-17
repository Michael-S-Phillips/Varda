"""One or more pixel-spectra plots per workspace, each in a reopenable dock."""

import PyQt6Ads as ads
import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QMainWindow

from varda.common.ui import VardaDockWidget
from varda.utilities.debug import generate_random_image
from varda.workspaces.pixel_spectra_docks import PixelSpectraDocks


@pytest.fixture
def image():
    return generate_random_image((20, 20, 10))


def _makeDocks(qtbot, **kwargs) -> tuple[QMainWindow, PixelSpectraDocks]:
    # The window must stay referenced for the test's duration: qtbot.addWidget
    # keeps only a weak reference, and deleting the window deletes every dock.
    window = QMainWindow()
    qtbot.addWidget(window)
    manager = ads.CDockManager(window)
    anchor = VardaDockWidget("ROI Plots")
    anchor.setWidget(QLabel("anchor"))
    manager.addDockWidget(ads.DockWidgetArea.BottomDockWidgetArea, anchor)
    return window, PixelSpectraDocks(manager, anchor, parent=window, **kwargs)


@pytest.fixture
def docks(qtbot):
    window, docks = _makeDocks(qtbot)
    yield docks
    del window


def test_first_plot_is_created_active(docks):
    plot = docks.newPlot()
    assert docks.active is plot
    assert docks.activeDock.widget() is plot
    assert "active" in docks.activeDock.windowTitle()


def test_selection_reopens_a_closed_active_dock(docks, image):
    docks.newPlot()
    docks.activeDock.toggleView(False)
    assert docks.activeDock.isClosed()

    curves = docks.addPixelSpectra([image], 1, 1)

    assert len(curves) == 1
    assert not docks.activeDock.isClosed()


def test_new_plot_becomes_the_target_and_titles_are_numbered(docks, image):
    first = docks.newPlot()
    second = docks.newPlot()
    assert docks.active is second
    assert docks.dockFor(second).windowTitle().startswith("Pixel Spectra 2")

    docks.addPixelSpectra([image], 1, 1)
    assert (len(first.pixelCurves), len(second.pixelCurves)) == (0, 1)

    docks.setActive(first)
    docks.addPixelSpectra([image], 3, 3)
    assert (len(first.pixelCurves), len(second.pixelCurves)) == (1, 1)
    assert "active" in docks.dockFor(first).windowTitle()
    assert "active" not in docks.dockFor(second).windowTitle()


def test_checking_receives_clicks_on_a_plot_makes_it_active(docks):
    first = docks.newPlot()
    second = docks.newPlot()

    first.activeCheckBox.setChecked(True)

    assert docks.active is first
    assert not second.activeCheckBox.isChecked()


def test_unchecking_the_only_active_plot_keeps_it_active(docks):
    plot = docks.newPlot()
    plot.activeCheckBox.setChecked(False)
    assert docks.active is plot
    assert plot.activeCheckBox.isChecked()


def test_clicking_inside_a_plot_makes_it_active(qtbot, docks):
    first = docks.newPlot()
    second = docks.newPlot()
    assert docks.active is second

    qtbot.mouseClick(first, Qt.MouseButton.LeftButton)

    assert docks.active is first
    assert first.activeCheckBox.isChecked()
    assert "active" in docks.dockFor(first).windowTitle()


def test_clicking_a_plots_dock_tab_makes_it_active(qtbot, docks):
    first = docks.newPlot()
    docks.newPlot()

    qtbot.mouseClick(docks.dockFor(first).tabWidget(), Qt.MouseButton.LeftButton)

    assert docks.active is first


def test_new_plot_button_opens_another_plot(docks):
    first = docks.newPlot()
    first.newPlotButton.click()
    assert len(docks.plots) == 2
    assert docks.active is docks.plots[1]


def test_configure_hook_runs_for_every_plot(qtbot):
    seen = []
    window, docks = _makeDocks(qtbot, configurePlot=seen.append)
    docks.newPlot()
    docks.newPlot()
    assert seen == docks.plots
    del window
