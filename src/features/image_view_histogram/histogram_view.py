# standard library
import logging
# third-party imports
import pyqtgraph as pg
from PyQt6.QtCore import pyqtSlot
from PyQt6.QtWidgets import QVBoxLayout, QWidget, QHBoxLayout,QTabWidget
from PyQt6.QtGui import QColor
from pyqtgraph import HistogramLUTItem

# local imports
from features.shared.selection_controls import StretchSelector, BandSelector
from .histogram_viewmodel import HistogramViewModel

logger = logging.getLogger(__name__)

class DualHistogram(QWidget):
    def __init__(self, parent=None, image=None, color=(255, 255, 255)):
        super().__init__(parent)
        self.color = color
        self.image = image
        self._initUI()
        self._connectSignals()

    def _initUI(self):
        # First (main) histogram
        self.histogram = pg.HistogramLUTWidget(
            self, image=self.image, orientation="horizontal"
        )
        self.histogram.item.regions[0].setBrush(QColor(*(*self.color, 25)))
        self.histogram.item.regions[0].setHoverBrush(QColor(*(*self.color, 50)))
        self.histogram.item.gradient.hide()
        self.histogram.item.fillHistogram(True, level=0.0, color=(*self.color, 50))
        self.histogram.item.disableAutoHistogramRange()

        # Second (zoomed) histogram
        self.histogramZoomed = pg.HistogramLUTWidget(
            self, image=self.image, orientation="horizontal"
        )
        zoomedColor = (self.color[0], self.color[1], self.color[2], 50)
        self.histogramZoomed.item.fillHistogram(True, level=0.0, color=zoomedColor)
        self.histogramZoomed.item.gradient.hide()
        self.histogramZoomed.item.regions[0].hide()
        self.histogramZoomed.item.vb.setMouseEnabled(x=False, y=False)

        # Layout: Stack two histograms vertically
        layout = QVBoxLayout()
        layout.addWidget(self.histogram)
        layout.addWidget(self.histogramZoomed)
        self.setLayout(layout)

    def _connectSignals(self):
        self.histogram.item.sigLevelsChanged.connect(self._handleLevelsChanged)

    def _handleLevelsChanged(self):
        mn, mx = self.histogram.item.getLevels()
        self.histogramZoomed.item.setHistogramRange(mn, mx)

class HistogramView(QWidget):
    """A basic view for editing band configurations of an image with selectable RGB histograms."""

    def __init__(self, viewModel: HistogramViewModel = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Histogram")
        self.viewModel = viewModel

        # To link the histograms to the image, we use an ImageItem.
        # This is just to leverage the existing functionality of the HistogramLUTWidget.
        self.imageItem = pg.ImageItem()
        self.imageItem.setImage(self.viewModel.getRasterFromBand())

        self._updatingHistograms = False
        self._initUI()
        self._connectSignals()

    def _initUI(self):
        self.tabWidget = QTabWidget()

        self.histogramR = DualHistogram(self, self.imageItem, color=(255, 0, 0))
        self.histogramG = DualHistogram(self, self.imageItem, color=(0, 255, 0))
        self.histogramB = DualHistogram(self, self.imageItem, color=(0, 0, 255))

        self.tabWidget.addTab(self.histogramR, "Red")
        self.tabWidget.addTab(self.histogramG, "Green")
        self.tabWidget.addTab(self.histogramB, "Blue")

        selectorLayout = QVBoxLayout()

        layout = QVBoxLayout()
        layout.addLayout(selectorLayout)
        layout.setContentsMargins(0, 20, 0, 0)
        layout.addWidget(self.tabWidget)
        self.setLayout(layout)

    def _connectSignals(self):
        self.viewModel.sigBandChanged.connect(self._onBandChanged)
        self.viewModel.sigStretchChanged.connect(self._onStretchChanged)

        self.histogramR.histogram.item.sigLevelsChanged.connect(self._onHistogramLevelsChanged)
        self.histogramG.histogram.item.sigLevelsChanged.connect(self._onHistogramLevelsChanged)
        self.histogramB.histogram.item.sigLevelsChanged.connect(self._onHistogramLevelsChanged)

    @pyqtSlot()
    def _onHistogramLevelsChanged(self):
        if self._updatingHistograms:
            return
        minR, maxR = self.histogramR.histogram.item.getLevels()
        minG, maxG = self.histogramG.histogram.item.getLevels()
        minB, maxB = self.histogramB.histogram.item.getLevels()

        self.viewModel.updateStretch(minR=minR, maxR=maxR, minG=minG, maxG=maxG, minB=minB, maxB=maxB)

    @pyqtSlot()
    def _onBandChanged(self):
        image = self.viewModel.getRasterFromBand()
        self.imageItem.setImage(image, autoLevels=False)

    @pyqtSlot(float, float, float, float, float, float)
    def _onStretchChanged(self, minR, maxR, minG, maxG, minB, maxB):

        self._updatingHistograms = True
        self.histogramR.histogram.item.setLevels(minR, maxR)
        self.histogramG.histogram.item.setLevels(minG, maxG)
        self.histogramB.histogram.item.setLevels(minB, maxB)
        self._updatingHistograms = False
