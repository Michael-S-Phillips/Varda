# standard library
import logging

# third-party imports
import pyqtgraph as pg
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSplitter
from PyQt6.QtCore import Qt

# local imports
from core.data import ProjectContext
from features.image_view_histogram import getHistogramView
from features.image_view_raster import getRasterView
from features.pixel_plot import PixelPlot

logger = logging.getLogger(__name__)

class GeneralImageAnalysis(QWidget):
    """
    Widget that composes several other basic views.
    Notably this lets us create connections between views,
     when those connections are too specific to make sense going through the ProjectContext.
     eg. Notifying a pixel plot when a user has clicked on a view.
    """
    def __init__(self, proj: ProjectContext, index, parent=None):
        super().__init__(parent)
        self.proj = proj
        self.index = index
        self.rasterView = None
        self.pixelPlot = None
        self.histogram = None
        self._initUI()
        self.connectSignals()

    def _initUI(self):
        self.label = QLabel("General Image Analysis", self)
        self.rasterView = getRasterView(self.proj, self.index, self)
        self.pixelPlot = PixelPlot(self.proj, self)
        self.histogram = getHistogramView(self.proj, self.index, self)

        splitter1 = QSplitter(Qt.Orientation.Vertical, self)
        splitter1.addWidget(self.rasterView)
        splitter1.addWidget(self.pixelPlot)

        splitter2 = QSplitter(Qt.Orientation.Horizontal, self)
        splitter2.addWidget(splitter1)
        splitter2.addWidget(self.histogram)

        # temp UI setup
        layout = QVBoxLayout()
        layout.setStretch(0, 2)
        layout.setStretch(1, 1)
        layout.addWidget(self.label)
        layout.addWidget(splitter2)
        self.setLayout(layout)

    def connectSignals(self):
        self.rasterView.sigImageClicked.connect(self.onImageClicked)

    def onImageClicked(self, xCoord: int, yCoord: int):
        logger.debug(f"Image click detected! Plotting: {xCoord}, {yCoord} from image {self.index}")
        self.pixelPlot.plot(self.index, (xCoord, yCoord))