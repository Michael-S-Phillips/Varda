# standard library
from typing import override

# third-party imports
import pyqtgraph as pg
from PyQt6.QtWidgets import QVBoxLayout, QWidget
from PyQt6.QtCore import Qt, QTimer

# local imports
from features.shared.selection_controls import StretchSelector
from .histogram_viewmodel import HistogramViewModel


class HistogramView(QWidget):
    """A basic view for editing band configurations of an image. Cannot create new
    parameters at the moment. only edit existing ones.
    """

    viewModel: HistogramViewModel
    bandSelector: StretchSelector
    updateTimer: QTimer

    def __init__(self, viewModel=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Histogram")
        self.viewModel = viewModel

        self._initUI()
        self._connectSignals()
        self.show()

    def _initUI(self):
        # Create GraphicsLayout
        graphicsLayout = pg.GraphicsLayout()
        graphicsLayout.setContentsMargins(0, 0, 0, 0)
        graphicsLayout.setSpacing(0)
        pass

    def _connectSignals(self):
        pass