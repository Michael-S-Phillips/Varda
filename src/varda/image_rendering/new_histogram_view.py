"""Histograms of the bands an image renderer displays, with the stretch range
drawn on top as a draggable region.

The X axis can be zoomed (wheel, drag; Shift/Ctrl/Cmd-drag zooms to a box).
Each zoom re-bins the histogram over the visible range and refits the Y axis,
so a distribution of valid values stays readable next to a stack of fill
values far out in the tail.
"""

import logging

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import QSignalBlocker
from PyQt6.QtWidgets import QStackedLayout, QTabWidget, QWidget

from varda.image_rendering.image_renderer import ImageRenderer, RenderMode
from varda.plotting.view_box import ModifierDragViewBox

logger = logging.getLogger(__name__)

BINS = 256


class NewHistogramView(QWidget):
    """A basic view for showing the histogram of an image's RGB data"""

    def __init__(self, imageRenderer: ImageRenderer, parent=None):
        super().__init__(parent)
        self.imageRenderer = imageRenderer
        self.imageRenderer.sigShouldRefresh.connect(self._updateHistogram)
        self.setWindowTitle("Histogram")
        ## Init UI ##
        self.tabWidget = QTabWidget()
        self.rPlot = self._makePlot()
        self.gPlot = self._makePlot()
        self.bPlot = self._makePlot()
        self.tabWidget.addTab(self.rPlot, "Red")
        self.tabWidget.addTab(self.gPlot, "Green")
        self.tabWidget.addTab(self.bPlot, "Blue")
        self.monoPlot = self._makePlot()

        # The values each plot shows and its curve, so a zoom can re-bin them
        self._values: dict[pg.PlotWidget, np.ndarray] = {}
        self._curves: dict[pg.PlotWidget, pg.PlotDataItem] = {}

        self.rRegion: pg.LinearRegionItem | None = None
        self.gRegion: pg.LinearRegionItem | None = None
        self.bRegion: pg.LinearRegionItem | None = None
        self.monoRegion: pg.LinearRegionItem | None = None

        layout = QStackedLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.tabWidget)
        layout.addWidget(self.monoPlot)
        layout.setCurrentIndex(0)
        self.setLayout(layout)

        self._updateHistogram()

    def _makePlot(self) -> pg.PlotWidget:
        plot = pg.PlotWidget(viewBox=ModifierDragViewBox())
        plot.setMouseEnabled(x=True, y=False)
        viewBox = plot.getViewBox()
        viewBox.setAutoVisible(y=True)  # Y fits what is visible in X
        viewBox.sigXRangeChanged.connect(lambda *_: self._rebin(plot))
        return plot

    def _updateHistogram(self):
        renderer = self.imageRenderer
        mode = renderer.settings.mode.get()
        self.layout().setCurrentIndex(1 if mode == RenderMode.MONO else 0)

        # clear curves (this also removes region items; they are re-added below)
        for plot in (self.rPlot, self.gPlot, self.bPlot, self.monoPlot):
            plot.clear()
        self._values.clear()
        self._curves.clear()

        minMaxVals = renderer.getMinMaxValues()
        if minMaxVals is not None:
            data = renderer.getRawBandData()
        else:
            data = renderer.getStretchedData()

        if mode == RenderMode.MONO:
            self._plotHistogram(data.ravel(), self.monoPlot, "w", (255, 255, 255, 50))
            self._syncMonoRegion(minMaxVals)
        else:
            self._plotHistogram(data[:, :, 0].ravel(), self.rPlot, "r", (255, 0, 0, 50))
            self._plotHistogram(data[:, :, 1].ravel(), self.gPlot, "g", (0, 255, 0, 50))
            self._plotHistogram(data[:, :, 2].ravel(), self.bPlot, "b", (0, 0, 255, 50))
            self._syncRgbRegions(minMaxVals)

    def _plotHistogram(self, values: np.ndarray, plot: pg.PlotWidget, pen, brush):
        values = values[np.isfinite(values)]
        if not values.size:
            return
        self._values[plot] = values
        x, y = _histogram(values, (float(values.min()), float(values.max())))
        self._curves[plot] = plot.plot(x, y, pen=pen, fillLevel=0, brush=brush)
        plot.getViewBox().enableAutoRange()  # a new image: show all of it

    def _rebin(self, plot: pg.PlotWidget) -> None:
        """Re-bin the plot's histogram over the visible X range."""
        values = self._values.get(plot)
        curve = self._curves.get(plot)
        if values is None or curve is None:
            return
        viewBox = plot.getViewBox()
        xMin, xMax = viewBox.viewRange()[0]
        if xMax <= xMin:
            return
        x, y = _histogram(values, (xMin, xMax))
        curve.setData(x, y)
        viewBox.enableAutoRange(axis=pg.ViewBox.YAxis)

    def _syncMonoRegion(self, minMaxVals):
        if minMaxVals is None:
            self.monoRegion = None
            return
        lo = float(np.ravel(minMaxVals[0])[0])
        hi = float(np.ravel(minMaxVals[1])[0])
        if self.monoRegion is None:
            self.monoRegion = pg.LinearRegionItem(
                values=(lo, hi), pen="w", brush=(0, 0, 0, 0), movable=True
            )
            self.monoRegion.sigRegionChangeFinished.connect(self._onMonoRegionChanged)
        else:
            with QSignalBlocker(self.monoRegion):
                self.monoRegion.setRegion((lo, hi))
        self.monoPlot.plotItem.addItem(self.monoRegion, ignoreBounds=True)

    def _onMonoRegionChanged(self):
        lo, hi = self.monoRegion.getRegion()
        self.imageRenderer.setStretchMinMax(0, lo, hi)

    def _syncRgbRegions(self, minMaxVals):
        if minMaxVals is None:
            self.rRegion = self.gRegion = self.bRegion = None
            return
        mins = np.ravel(minMaxVals[0])
        maxs = np.ravel(minMaxVals[1])
        specs = (
            ("rRegion", self.rPlot, "r", 0, self._onRRegionChanged),
            ("gRegion", self.gPlot, "g", 1, self._onGRegionChanged),
            ("bRegion", self.bPlot, "b", 2, self._onBRegionChanged),
        )
        for attr, plot, pen, channel, handler in specs:
            lo, hi = float(mins[channel]), float(maxs[channel])
            region = getattr(self, attr)
            if region is None:
                region = pg.LinearRegionItem(
                    values=(lo, hi), pen=pen, brush=(0, 0, 0, 0), movable=True
                )
                region.sigRegionChangeFinished.connect(handler)
                setattr(self, attr, region)
            else:
                with QSignalBlocker(region):
                    region.setRegion((lo, hi))
            plot.plotItem.addItem(region, ignoreBounds=True)

    def _onRRegionChanged(self):
        lo, hi = self.rRegion.getRegion()
        self.imageRenderer.setStretchMinMax(0, lo, hi)

    def _onGRegionChanged(self):
        lo, hi = self.gRegion.getRegion()
        self.imageRenderer.setStretchMinMax(1, lo, hi)

    def _onBRegionChanged(self):
        lo, hi = self.bRegion.getRegion()
        self.imageRenderer.setStretchMinMax(2, lo, hi)


def _histogram(
    values: np.ndarray, valueRange: tuple[float, float]
) -> tuple[np.ndarray, np.ndarray]:
    """Bin centres and counts of ``values`` within ``valueRange``."""
    lo, hi = valueRange
    if lo == hi:
        lo, hi = lo - 0.5, hi + 0.5
    counts, edges = np.histogram(values, bins=BINS, range=(lo, hi))
    return (edges[:-1] + edges[1:]) / 2.0, counts
