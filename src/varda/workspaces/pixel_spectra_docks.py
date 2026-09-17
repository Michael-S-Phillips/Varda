"""One or more pixel-spectra plots for a workspace, each in its own dock."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import PyQt6Ads as ads
from PyQt6.QtCore import QEvent, QObject, QSignalBlocker
from PyQt6.QtWidgets import QApplication, QWidget

from varda.common.entities import VardaRaster
from varda.common.ui import VardaDockWidget
from varda.plotting.pixel_spectra_plot import PixelSpectraPlotWidget
from varda.plotting.plot import Curve

BASE_TITLE = "Pixel Spectra"


class PixelSpectraDocks(QObject):
    """Owns a workspace's pixel-spectra plots.

    Exactly one plot is *active* and receives pixel selections. Closing a dock
    only hides it; the next selection re-shows the active one, so a closed plot
    is never a dead end. Additional plots let spectra from different regions be
    collected side by side.
    """

    def __init__(
        self,
        dockManager: ads.CDockManager,
        anchor: ads.CDockWidget,
        *,
        configurePlot: Callable[[PixelSpectraPlotWidget], None] | None = None,
        parent: QObject | None = None,
    ) -> None:
        """New docks are tabbed alongside ``anchor`` (then alongside the previous
        pixel plot). ``configurePlot`` runs on each new plot, e.g. to add
        workspace-specific sidebar sections."""
        super().__init__(parent)
        self._dockManager = dockManager
        self._anchor = anchor
        self._configurePlot = configurePlot
        self.plots: list[PixelSpectraPlotWidget] = []
        self._docks: dict[PixelSpectraPlotWidget, VardaDockWidget] = {}
        self._baseTitles: dict[PixelSpectraPlotWidget, str] = {}
        self._active: PixelSpectraPlotWidget | None = None
        # Clicking in a plot, or on its dock tab, makes it the active one; those
        # presses go to child widgets, so watch them application-wide.
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

    def eventFilter(self, a0: QObject | None, a1: QEvent | None) -> bool:
        if (
            a1 is not None
            and a1.type() == QEvent.Type.MouseButtonPress
            and isinstance(a0, QWidget)
        ):
            clicked = self._plotAt(a0)
            if clicked is not None and clicked is not self._active:
                self.setActive(clicked)
        return False

    def _plotAt(self, widget: QWidget) -> PixelSpectraPlotWidget | None:
        for plot in self.plots:
            tab = self._docks[plot].tabWidget()
            if _within(widget, plot) or (tab is not None and _within(widget, tab)):
                return plot
        return None

    @property
    def active(self) -> PixelSpectraPlotWidget:
        """The plot receiving pixel selections (created on demand)."""
        if self._active is None:
            return self.newPlot()
        return self._active

    @property
    def activeDock(self) -> VardaDockWidget:
        return self.dockFor(self.active)

    def dockFor(self, plot: PixelSpectraPlotWidget) -> VardaDockWidget:
        return self._docks[plot]

    def newPlot(self) -> PixelSpectraPlotWidget:
        """Open another pixel-spectra plot and make it the active one."""
        plot = PixelSpectraPlotWidget()
        number = len(self.plots) + 1
        title = BASE_TITLE if number == 1 else f"{BASE_TITLE} {number}"
        dock = VardaDockWidget(title)
        dock.setWidget(plot)

        neighbour = self._docks[self.plots[-1]] if self.plots else self._anchor
        self.plots.append(plot)
        self._docks[plot] = dock
        self._baseTitles[plot] = title
        if self._configurePlot is not None:
            self._configurePlot(plot)

        plot.newPlotButton.clicked.connect(lambda: self.newPlot())
        plot.activeCheckBox.toggled.connect(
            lambda checked, plot=plot: self._onActiveToggled(plot, checked)
        )

        area = neighbour.dockAreaWidget()
        if area is not None:
            self._dockManager.addDockWidget(
                ads.DockWidgetArea.CenterDockWidgetArea, dock, area
            )
        else:
            self._dockManager.addDockWidget(
                ads.DockWidgetArea.BottomDockWidgetArea, dock
            )

        self.setActive(plot)
        return plot

    def setActive(self, plot: PixelSpectraPlotWidget) -> None:
        self._active = plot
        for candidate in self.plots:
            isActive = candidate is plot
            with QSignalBlocker(candidate.activeCheckBox):
                candidate.activeCheckBox.setChecked(isActive)
            base = self._baseTitles[candidate]
            self._docks[candidate].setWindowTitle(
                f"{base} (active)" if isActive else base
            )

    def addPixelSpectra(
        self,
        images: Sequence[VardaRaster],
        x: int,
        y: int,
        *,
        labelWithImageName: bool = False,
    ) -> list[Curve]:
        """Plot a selection on the active plot, re-showing its dock if closed."""
        return self._shownActivePlot().addPixelSpectra(
            images, x, y, labelWithImageName=labelWithImageName
        )

    def addSpectrum(self, wavelengths, values, label: str) -> Curve:
        """Plot any spectrum on the active plot, re-showing its dock if closed."""
        return self._shownActivePlot().addSpectrum(wavelengths, values, label)

    def addSpectra(self, entries: Sequence[tuple]) -> list[Curve]:
        """Plot several spectra as one selection on the active plot."""
        return self._shownActivePlot().addSpectra(entries)

    def _shownActivePlot(self) -> PixelSpectraPlotWidget:
        plot = self.active
        dock = self.dockFor(plot)
        if dock.isClosed():
            dock.toggleView(True)
        return plot

    def _onActiveToggled(self, plot: PixelSpectraPlotWidget, checked: bool) -> None:
        if checked:
            self.setActive(plot)
        elif plot is self._active:
            # exactly one plot stays active
            with QSignalBlocker(plot.activeCheckBox):
                plot.activeCheckBox.setChecked(True)


def _within(widget: QWidget, container: QWidget) -> bool:
    return widget is container or container.isAncestorOf(widget)
