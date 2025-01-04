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
    viewModel: BandViewModel
    rBandSlider: pg.InfiniteLine
    gBandSlider: pg.InfiniteLine
    bBandSlider: pg.InfiniteLine
    bandSelector: StretchSelector
    widgetHeight = 152
    updateInterval = 20

    def __init__(self, viewModel=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Band Editor")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)

        self.viewModel = viewModel

        self.initUI()
        self.connectSignals()

        self.setMaximumHeight(self.widgetHeight)

        self.updateTimer = QTimer()
        self.updateTimer.setSingleShot(True)
        self.updateTimer.timeout.connect(self.updateBand)
        self.isDragging = False
        self.show()

    def initUI(self):
        bounds = [0, self.viewModel.getBandRange()]

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

        # GraphicsView setup
        view = pg.GraphicsView(parent=self)
        view.setCentralItem(graphicsLayout)

        # Sliders setup
        self.rBandSlider = pg.InfiniteLine(
            movable=True, angle=90, pen="r", bounds=bounds
        )
        self.gBandSlider = pg.InfiniteLine(
            movable=True, angle=90, pen="g", bounds=bounds
        )
        self.bBandSlider = pg.InfiniteLine(
            movable=True, angle=90, pen="b", bounds=bounds
        )

        # initialize labels for each slider
        self.MyInfLineLabel(
            self.rBandSlider, text="{value}", position=0.5, anchor=(0, 0.5)
        )
        self.MyInfLineLabel(
            self.gBandSlider, text="{value}", position=0.5, anchor=(0, 0.5)
        )
        self.MyInfLineLabel(
            self.bBandSlider, text="{value}", position=0.5, anchor=(0, 0.5)
        )

        # Add sliders to the ViewBox
        vbox.addItem(self.rBandSlider)
        vbox.addItem(self.gBandSlider)
        vbox.addItem(self.bBandSlider)

        # setup Band selector
        # directly accessing these attributes is cheating a little bit but its fine lol
        self.bandSelector = StretchSelector(self.viewModel.proj, self.viewModel.index)

        # Layout setup
        layout = QVBoxLayout()
        layout.addWidget(self.bandSelector)
        layout.addWidget(view)
        self.setLayout(layout)

    def connectSignals(self):
        self.viewModel.sigBandChanged.connect(self.onBandChanged)
        self.bandSelector.currentIndexChanged.connect(self.viewModel.selectBand)
        self.rBandSlider.sigPositionChanged.connect(self.onSliderMoved)
        self.gBandSlider.sigPositionChanged.connect(self.onSliderMoved)
        self.bBandSlider.sigPositionChanged.connect(self.onSliderMoved)

    def onBandChanged(self):
        band = self.viewModel.getSelectedBand()
        self.rBandSlider.setValue(band.r)
        self.gBandSlider.setValue(band.g)
        self.bBandSlider.setValue(band.b)

    def onSliderMoved(self):
        if not self.isDragging:
            self.isDragging = True
            self.updateTimer.start(
                self.updateInterval
            )  # Update interval in milliseconds

    def updateBand(self):
        self.viewModel.updateBand(
            self.rBandSlider.value(), self.gBandSlider.value(), self.bBandSlider.value()
        )

        if self.isDragging:
            self.updateTimer.start(
                self.updateInterval
            )  # Restart the timer for continuous updates
        self.isDragging = False

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
