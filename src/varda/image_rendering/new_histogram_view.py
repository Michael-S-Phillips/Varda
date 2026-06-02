# varda/features/image_view_histogram/histogram_view.py
import numpy as np

import varda

# standard library
import logging

# third-party imports
import pyqtgraph as pg
from PyQt6.QtCore import QSignalBlocker
from PyQt6.QtWidgets import (
    QVBoxLayout,
    QWidget,
    QTabWidget,
    QStackedWidget,
    QStackedLayout,
)

# local imports
from varda.image_rendering.image_renderer import (
    ImageRenderer,
    RendererSettings,
    RenderMode,
    RendererSettingsPanel,
)

logger = logging.getLogger(__name__)


class NewHistogramView(QWidget):
    """A basic view for showing the histogram of an image's RGB data"""

    def __init__(self, imageRenderer: ImageRenderer, parent=None):
        super().__init__(parent)
        self.imageRenderer = imageRenderer
        self.imageRenderer.sigShouldRefresh.connect(self._updateHistogram)
        self.setWindowTitle("Histogram")
        ## Init UI ##
        self.tabWidget = QTabWidget()
        self.rPlot = pg.PlotWidget()
        self.gPlot = pg.PlotWidget()
        self.bPlot = pg.PlotWidget()
        self.rPlot.setMouseEnabled(x=False, y=False)
        self.gPlot.setMouseEnabled(x=False, y=False)
        self.bPlot.setMouseEnabled(x=False, y=False)

        self.tabWidget.addTab(self.rPlot, "Red")
        self.tabWidget.addTab(self.gPlot, "Green")
        self.tabWidget.addTab(self.bPlot, "Blue")

        self.monoPlot = pg.PlotWidget()
        self.monoPlot.setMouseEnabled(x=False, y=False)

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

    def _updateHistogram(self):
        renderer = self.imageRenderer
        mode = renderer.settings.mode.get()
        self.layout().setCurrentIndex(1 if mode == RenderMode.MONO else 0)

        # clear curves (this also removes region items; they are re-added below)
        self.rPlot.clear()
        self.gPlot.clear()
        self.bPlot.clear()
        self.monoPlot.clear()

        minMaxVals = renderer.getMinMaxValues()
        if minMaxVals is not None:
            data = renderer.getRawBandData()
        else:
            data = renderer.getStretchedData()

        def plotHistogram(arr, plotWidget, pen, brush):
            if arr.size:
                vmin, vmax = np.nanmin(arr), np.nanmax(arr)
                if vmin == vmax:
                    vmin -= 0.5
                    vmax += 0.5
                y, x = np.histogram(arr, bins=256, range=(vmin, vmax))
                plotWidget.plot(x[1:], y, pen=pen, fillLevel=0, brush=brush)

        if mode == RenderMode.MONO:
            plotHistogram(data.ravel(), self.monoPlot, "w", (255, 255, 255, 50))
            self._syncMonoRegion(minMaxVals)
        else:
            plotHistogram(data[:, :, 0].ravel(), self.rPlot, "r", (255, 0, 0, 50))
            plotHistogram(data[:, :, 1].ravel(), self.gPlot, "g", (0, 255, 0, 50))
            plotHistogram(data[:, :, 2].ravel(), self.bPlot, "b", (0, 0, 255, 50))
            self._syncRgbRegions(minMaxVals)

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
        self.monoPlot.addItem(self.monoRegion)

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
            plot.addItem(region)

    def _onRRegionChanged(self):
        lo, hi = self.rRegion.getRegion()
        self.imageRenderer.setStretchMinMax(0, lo, hi)

    def _onGRegionChanged(self):
        lo, hi = self.gRegion.getRegion()
        self.imageRenderer.setStretchMinMax(1, lo, hi)

    def _onBRegionChanged(self):
        lo, hi = self.bRegion.getRegion()
        self.imageRenderer.setStretchMinMax(2, lo, hi)


if __name__ == "__main__":
    q_app = pg.mkQApp()
    image = varda.utilities.debug.generate_random_image((100, 100, 10), (10, 10, 10))
    renderSettings = RendererSettings(image)
    renderSettings.mode.set(RenderMode.RGB)
    renderer = ImageRenderer(image, renderSettings)
    settingsPanel = renderer.getSettingsPanel()

    view = NewHistogramView(renderer)
    view.show()
    settingsPanel.show()
    q_app.exec()
