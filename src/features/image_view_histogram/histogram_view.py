# standard library

# third-party imports
import pyqtgraph as pg
from PyQt6.QtWidgets import QVBoxLayout, QWidget, QHBoxLayout
from PyQt6.QtGui import QColor

# local imports
from features.shared.selection_controls import StretchSelector, BandSelector
from .histogram_viewmodel import HistogramViewModel


class DualHistogram(QWidget):
    def __init__(self, parent=None, image=None, color=(255, 255, 255, 50)):
        super().__init__(parent)
        self.color = color
        self.image = image
        self._initUI()
        self._connectSignals()

    def _initUI(self):
        self.histogram = pg.HistogramLUTWidget(
            self, image=self.image, orientation="horizontal"
        )
        self.histogram.item.regions[0].setBrush(QColor(*self.color))
        self.histogram.item.gradient.hide()
        self.histogram.item.fillHistogram(True, level=0.0, color=self.color)
        self.histogramZoomed = pg.HistogramLUTWidget(
            self, image=self.image, orientation="horizontal"
        )
        zoomedColor = (self.color[0], self.color[1], self.color[2], 50)
        self.histogramZoomed.item.fillHistogram(True, level=0.0, color=zoomedColor)
        self.histogramZoomed.item.gradient.hide()
        self.histogramZoomed.item.regions[0].hide()
        self.histogramZoomed.item.vb.setMouseEnabled(x=False, y=False)
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
    """A basic view for editing band configurations of an image. Cannot create new
    parameters at the moment. only edit existing ones.
    """

    viewModel: HistogramViewModel
    bandSelector: BandSelector
    stretchSelector: StretchSelector
    histogramR: DualHistogram
    histogramG: DualHistogram
    histogramB: DualHistogram
    imageItem: pg.ImageItem

    def __init__(self, viewModel=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Histogram")
        self.viewModel = viewModel
        self.imageItem = pg.ImageItem()
        self.imageItem.setImage(self.viewModel.getRasterFromBand())
        self._initUI()
        self._connectSignals()

    def _initUI(self):
        self.histogramR = DualHistogram(self, self.imageItem, color=(255, 0, 0, 25))
        self.histogramG = DualHistogram(self, self.imageItem, color=(0, 255, 0, 25))
        self.histogramB = DualHistogram(self, self.imageItem, color=(0, 0, 255, 25))

        self.bandSelector = BandSelector(
            self.viewModel.proj, self.viewModel.index, self
        )

        self.stretchSelector = StretchSelector(
            self.viewModel.proj, self.viewModel.index, self
        )

        selectorLayout = QHBoxLayout()
        selectorLayout.addWidget(self.bandSelector)
        selectorLayout.addWidget(self.stretchSelector)

        layout = QVBoxLayout()
        layout.addLayout(selectorLayout)
        layout.addWidget(self.histogramR)
        layout.addWidget(self.histogramG)
        layout.addWidget(self.histogramB)
        self.setLayout(layout)

    def _connectSignals(self):
        self.viewModel.sigBandChanged.connect(self._onBandChanged)
        self.viewModel.sigStretchChanged.connect(self._onStretchChanged)

        self.histogramR.histogram.sigLevelsChanged.connect(self._handleLevelsChanged)
        self.histogramG.histogram.sigLevelsChanged.connect(self._handleLevelsChanged)
        self.histogramB.histogram.sigLevelsChanged.connect(self._handleLevelsChanged)

        self.bandSelector.currentIndexChanged.connect(self.viewModel.selectBand)
        self.stretchSelector.currentIndexChanged.connect(self.viewModel.selectStretch)

    def _handleLevelsChanged(self):
        minR, maxR = self.histogramR.histogram.item.getLevels()
        minG, maxG = self.histogramG.histogram.item.getLevels()
        minB, maxB = self.histogramB.histogram.item.getLevels()
        self.viewModel.updateStretch(minR, maxR, minG, maxG, minB, maxB)

    def _onBandChanged(self):
        image = self.viewModel.getRasterFromBand()
        self.imageItem.setImage(image)

    def _onStretchChanged(self):
        stretch = self.viewModel.getSelectedStretch()
        self.histogramR.histogram.item.setLevels(stretch.minR, stretch.maxR)
        self.histogramG.histogram.item.setLevels(stretch.minG, stretch.maxG)
        self.histogramB.histogram.item.setLevels(stretch.minB, stretch.maxB)
