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
        self.rRegion = None
        self.gRegion = None
        self.bRegion = None

        self.tabWidget.addTab(self.rPlot, "Red")
        self.tabWidget.addTab(self.gPlot, "Green")
        self.tabWidget.addTab(self.bPlot, "Blue")

        self.monoPlot = pg.PlotWidget()
        self.monoPlot.setMouseEnabled(x=False, y=False)
        self.monoRegion = None

        layout = QStackedLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.tabWidget)
        layout.addWidget(self.monoPlot)
        layout.setCurrentIndex(0)
        self.setLayout(layout)

        self._updateHistogram()

    def _updateHistogram(self):
        if self.imageRenderer.settings.mode == "mono":
            self.layout().setCurrentIndex(1)
        elif self.imageRenderer.settings.mode == "rgb":
            self.layout().setCurrentIndex(0)

        def plotHistogram(arr, plotWidget, pen, brush):
            if arr.size:
                vmin, vmax = arr.min(), arr.max()

                if vmin == vmax:
                    vmin -= 0.5
                    vmax += 0.5
                y, x = np.histogram(arr, bins=256, range=(vmin, vmax))
                plotWidget.plot(
                    x[1:],
                    y,
                    pen=pen,
                    fillLevel=0,
                    brush=brush,
                )

        # clear old plots
        self.rPlot.clear()
        self.gPlot.clear()
        self.bPlot.clear()
        self.monoPlot.clear()

        # plot new ones
        mode = self.imageRenderer.settings.mode

        if self.imageRenderer.isLinearStretch():
            data = self.imageRenderer.getRawBandData()
        else:
            data = self.imageRenderer.getStretchedData()

        minMaxVals = self.imageRenderer.getMinMaxValues()
        if mode == "mono":
            plotHistogram(data.ravel(), self.monoPlot, "w", (255, 255, 255, 50))
        elif mode == "rgb":
            print(f"RGB data shape: {data.shape}")
            plotHistogram(data[:, :, 0].ravel(), self.rPlot, "r", (255, 0, 0, 50))
            plotHistogram(data[:, :, 1].ravel(), self.gPlot, "g", (0, 255, 0, 50))
            plotHistogram(data[:, :, 2].ravel(), self.bPlot, "b", (0, 0, 255, 50))

        if minMaxVals is not None and mode == "mono":
            self.monoRegion = pg.LinearRegionItem(
                values=minMaxVals,
                pen="w",
                brush=(0, 0, 0, 0),
                movable=False,
            )
            self.monoPlot.addItem(self.monoRegion)

        elif minMaxVals is not None and mode == "rgb":
            print(f"RGB min max vals: {minMaxVals}")
            self.rRegion = pg.LinearRegionItem(
                values=(minMaxVals[0][0], minMaxVals[1][0]),
                pen="r",
                brush=(0, 0, 0, 0),
                movable=False,
            )
            self.rPlot.addItem(self.rRegion)

            self.gRegion = pg.LinearRegionItem(
                values=(minMaxVals[0][1], minMaxVals[1][1]),
                pen="g",
                brush=(0, 0, 0, 0),
                movable=False,
            )
            self.gPlot.addItem(self.gRegion)

            self.bRegion = pg.LinearRegionItem(
                values=(minMaxVals[0][2], minMaxVals[1][2]),
                pen="b",
                brush=(0, 0, 0, 0),
                movable=False,
            )
            self.bPlot.addItem(self.bRegion)

        elif minMaxVals is None and mode == "mono":
            self.monoPlot.removeItem(self.monoRegion)

        elif minMaxVals is None and mode == "rgb":
            self.rPlot.removeItem(self.rRegion)
            self.gPlot.removeItem(self.gRegion)
            self.bPlot.removeItem(self.bRegion)


if __name__ == "__main__":
    q_app = pg.mkQApp()
    image = varda.utilities.debug.generateRandomImage((100, 100, 10), (10, 10, 10))
    renderSettings = RendererSettings()
    renderSettings.bands = np.array([0, 1, 2])
    settingsPanel = RendererSettingsPanel(image, renderSettings)
    renderer = ImageRenderer(image, renderSettings)
    settingsPanel.sigSettingsChanged.connect(renderer.updateSettings)

    view = NewHistogramView(renderer)
    renderer.sigShouldRefresh.connect(view._updateHistogram)
    view.show()
    settingsPanel.show()
    q_app.exec()
