# standard library
from typing import override

# third-party imports
import pyqtgraph as pg
from PyQt6.QtWidgets import QVBoxLayout, QWidget
from PyQt6.QtCore import Qt, QTimer

# local imports
from features.shared.selection_controls import StretchSelector
from .band_viewmodel import BandViewModel


class BandView(QWidget):
    """A basic view for editing band configurations of an image. Cannot create new
    parameters at the moment. only edit existing ones.
    """

    viewModel: BandViewModel
    rBandSlider: pg.InfiniteLine
    gBandSlider: pg.InfiniteLine
    bBandSlider: pg.InfiniteLine
    bandSelector: StretchSelector
    widgetHeight = 152
    updateTimer: QTimer

    def __init__(self, viewModel=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Band Editor")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        self.setMaximumHeight(self.widgetHeight)
        self.viewModel = viewModel

        self._initUI()
        self._connectSignals()
        self.show()

    def _initUI(self):
        bounds = [0, self.viewModel.getBandCount()]

        # Create GraphicsLayout
        graphicsLayout = pg.GraphicsLayout()
        graphicsLayout.setContentsMargins(0, 0, 0, 0)
        graphicsLayout.setSpacing(0)

        # ViewBox setup
        vbox = pg.ViewBox()
        vbox.setRange(xRange=bounds, yRange=(-1, 1))
        vbox.setMaximumHeight(self.widgetHeight)
        vbox.setMinimumHeight(45)
        vbox.setMouseEnabled(x=False, y=False)
        vbox.setAspectLocked(lock=False)
        graphicsLayout.addItem(vbox, row=0, col=0)

        # Axis setup
        axis = pg.AxisItem(orientation="bottom")
        axis.linkToView(vbox)
        graphicsLayout.addItem(axis, row=1, col=0)

        # Sliders setup
        self.rBandSlider = pg.InfiniteLine(0, 90, "r", True, bounds)
        self.gBandSlider = pg.InfiniteLine(0, 90, "g", True, bounds)
        self.bBandSlider = pg.InfiniteLine(0, 90, "b", True, bounds)

        # initialize labels for each slider
        self.MyInfLineLabel(self.rBandSlider, "{value}", False, 0.5, [(0, 0.5)])
        self.MyInfLineLabel(self.gBandSlider, "{value}", False, 0.5, [(0, 0.5)])
        self.MyInfLineLabel(self.bBandSlider, "{value}", False, 0.5, [(0, 0.5)])

        # Add sliders to the ViewBox
        vbox.addItem(self.rBandSlider)
        vbox.addItem(self.gBandSlider)
        vbox.addItem(self.bBandSlider)

        # setup Band selector
        self.bandSelector = StretchSelector(
            self.viewModel.proj, self.viewModel.imageIndex
        )

        # GraphicsView setup
        view = pg.GraphicsView(parent=self)
        view.setCentralItem(graphicsLayout)

        # Layout setup
        layout = QVBoxLayout()
        #layout.setContentsMargins(0, 20, 0, 20)
        layout.addWidget(self.bandSelector)
        layout.addWidget(view)
        self.setLayout(layout)

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

    def _onBandChanged(self, r, g, b):
        self.rBandSlider.setValue(r)
        self.gBandSlider.setValue(g)
        self.bBandSlider.setValue(b)

    # pylint: disable=abstract-method
    class MyInfLineLabel(pg.InfLineLabel):
        """Custom label for InfiniteLine, just so we can round the displayed value to an
        integer"""

        @override
        def valueChanged(self):
            if not self.isVisible():
                return
            value = int(self.line.value())
            self.setText(self.format.format(value=value))
            self.updatePosition()
