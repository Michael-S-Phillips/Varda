# standard library
from typing import override, List, Tuple
import logging

# third-party imports
import pyqtgraph as pg
from PyQt6.QtWidgets import QVBoxLayout, QWidget
from PyQt6.QtCore import Qt, QTimer, pyqtSlot

# local imports
from .band_viewmodel import BandViewModel

logger = logging.getLogger(__name__)

class BandView(QWidget):
    """A basic view for editing band configurations of an image. Cannot create new
    parameters at the moment. only edit existing ones.
    """

    viewModel: BandViewModel
    rBandSlider: pg.InfiniteLine
    gBandSlider: pg.InfiniteLine
    bBandSlider: pg.InfiniteLine
    widgetHeight = 152
    updateTimer: QTimer

    def __init__(self, viewModel=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Band Editor")
        # self.setMaximumHeight(self.widgetHeight)
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
        vbox.setRange(xRange=self.viewModel.bounds, yRange=(-1, 1))
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
        self.rBandSlider = pg.InfiniteLine(0, 90, "r", True, self.viewModel.bounds)
        self.gBandSlider = pg.InfiniteLine(0, 90, "g", True, self.viewModel.bounds)
        self.bBandSlider = pg.InfiniteLine(0, 90, "b", True, self.viewModel.bounds)

        # initialize labels for each slider
        self.MyInfLineLabel(self.viewModel, self.rBandSlider, "{value}", False, 0.5 )
        self.MyInfLineLabel(self.viewModel, self.gBandSlider, "{value}", False, 0.5 )
        self.MyInfLineLabel(self.viewModel, self.bBandSlider, "{value}", False, 0.5 )

        # Add sliders to the ViewBox
        vbox.addItem(self.rBandSlider)
        vbox.addItem(self.gBandSlider)
        vbox.addItem(self.bBandSlider)

        # GraphicsView setup
        view = pg.GraphicsView(parent=self)
        view.setCentralItem(graphicsLayout)

        # Layout setup
        layout = QVBoxLayout()
        #layout.setContentsMargins(0, 20, 0, 20)
        layout.addWidget(view)
        self.setLayout(layout)

    def _connectSignals(self):
        self.viewModel.sigBandChanged.connect(self._onBandChanged)
        self.rBandSlider.sigPositionChanged.connect(
            lambda: self._onSliderChanged(self.rBandSlider)
        )
        self.gBandSlider.sigPositionChanged.connect(
            lambda: self._onSliderChanged(self.gBandSlider)
        )
        self.bBandSlider.sigPositionChanged.connect(
            lambda: self._onSliderChanged(self.bBandSlider)
        )

    @pyqtSlot(pg.InfiniteLine)
    def _onSliderChanged(self, slider):
        # clamp slider to the range of the image wavelengths
        minValue, maxValue = self.viewModel.bounds
        logger.debug(f"minValue: {minValue} maxValue {maxValue}")
        slider.setValue(max(min(slider.value(), maxValue), minValue))


        # update the correct band
        if slider is self.rBandSlider:
            self.viewModel.updateBand(r=slider.value())
        elif slider is self.gBandSlider:
            self.viewModel.updateBand(g=slider.value())
        elif slider is self.bBandSlider:
            self.viewModel.updateBand(b=slider.value())

    @pyqtSlot(float, float, float)
    def _onBandChanged(self, r, g, b):
        self.rBandSlider.setValue(self.viewModel.getIndexOfWavelength(r))
        self.gBandSlider.setValue(self.viewModel.getIndexOfWavelength(g))
        self.bBandSlider.setValue(self.viewModel.getIndexOfWavelength(b))

    # pylint: disable=abstract-method
    class MyInfLineLabel(pg.InfLineLabel):
        """Custom label for InfiniteLine, just so we can round the displayed value to an
        integer"""
        def __init__(self, viewModel, line, text, movable, position, **kwargs):
            self.bandViewModel = viewModel
            super().__init__(line, text, movable, position, **kwargs)

        @override
        def valueChanged(self):
            if not self.isVisible():
                return

            index = self.bandViewModel.getIndexOfWavelength(self.line.value())
            text = self.bandViewModel.getWavelengthAt(index)
            self.setText(self.format.format(value=text))
            self.updatePosition()
