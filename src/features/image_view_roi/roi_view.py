# standard library
from typing import override

# third-party imports
import pyqtgraph as pg
from PyQt6.QtWidgets import QVBoxLayout, QWidget
from PyQt6.QtCore import Qt, QTimer

# local imports
from features.shared.selection_controls import StretchSelector
from .roi_viewmodel import ROIViewModel


class ROIView(QWidget):
    """A view for viewing and selecting ROIs that have been drawn
    on the main rasterview"""

    viewModel: ROIViewModel
    widgetHeight = 300
    updateTimer: QTimer

    def __init__(self, viewModel=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ROIs for image " + viewModel.imageIndex)
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        self.setMaximumHeight(self.widgetHeight)
        self.viewModel = viewModel

        self._initUI()
        self._connectSignals()
        self.show()

    def _initUI(self):

        # Create GraphicsLayout
        graphicsLayout = pg.GraphicsLayout()
        graphicsLayout.setContentsMargins(0, 0, 0, 0)
        graphicsLayout.setSpacing(0)

        # ViewBox setup
        vbox = pg.ViewBox()
        # set up the view box

    def _connectSignals(self):
        self.viewModel.sigBandChanged.connect(self._onBandChanged)
        self.bandSelector.currentIndexChanged.connect(self.viewModel.selectBand)
        self.rBandSlider.sigPositionChanged.connect(
            lambda: self.viewModel.updateBand(r=self.rBandSlider.value())
        )
        self.gBandSlider.sigPositionChanged.connect(
            lambda: self.viewModel.updateBand(g=self.gBandSlider.value())
        )
        self.bBandSlider.sigPositionChanged.connect(
            lambda: self.viewModel.updateBand(b=self.bBandSlider.value())
        )

