
# standard library
from typing import override

# third-party imports
import pyqtgraph as pg
from PyQt6.QtWidgets import QVBoxLayout
from PyQt6.QtCore import Qt, QTimer

# local imports
from gui.views.baseimageview import BaseImageView


class ImageViewBandEditor(BaseImageView):

    widgetHeight = 152
    updateInterval = 20

    def __init__(self, imageModel=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Band Editor")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        self.vbox = None
        self.axis = None
        self.graphics = None
        self.rBandSlider = None
        self.gBandSlider = None
        self.bBandSlider = None
        self.rBandLabel = None
        self.gBandLabel = None
        self.bBandLabel = None

        self.initUI()
        self.setImageModel(imageModel)
        self.setMaximumHeight(self.widgetHeight)

        self.updateTimer = QTimer()
        self.updateTimer.setSingleShot(True)
        self.updateTimer.timeout.connect(self.updateModel)
        self.isDragging = False

        self.show()

    def setImageModel(self, image):
        super().setImageModel(image)
        self.vbox.setRange(xRange=(0, self._imageModel.bandCount - 1))
        self.onBandChanged()

    def initUI(self):
        # Create GraphicsLayout
        self.layout = pg.GraphicsLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # Axis setup
        self.axis = pg.AxisItem(orientation='bottom')

        # ViewBox setup
        self.vbox = pg.ViewBox()
        self.vbox.setMaximumHeight(self.widgetHeight)
        self.vbox.setMinimumHeight(45)
        self.vbox.setMouseEnabled(x=False, y=False)

        # Set aspect ratio to avoid axis distortion
        self.vbox.setAspectLocked(lock=False)

        # Add the ViewBox to the layout
        self.layout.addItem(self.vbox, row=0, col=0)

        # Add the axis to the layout, below the ViewBox
        self.layout.addItem(self.axis, row=1, col=0)

        # Link axis to ViewBox
        self.axis.linkToView(self.vbox)

        # GraphicsView setup
        self.view = pg.GraphicsView()
        self.view.setCentralItem(self.layout)

        # Add sliders to the ViewBox
        self.rBandSlider = pg.InfiniteLine(movable=True, angle=90, pen='r')
        self.gBandSlider = pg.InfiniteLine(movable=True, angle=90, pen='g')
        self.bBandSlider = pg.InfiniteLine(movable=True, angle=90, pen='b')

        self.rBandSlider.sigPositionChanged.connect(self.onSliderMoved)
        self.gBandSlider.sigPositionChanged.connect(self.onSliderMoved)
        self.bBandSlider.sigPositionChanged.connect(self.onSliderMoved)

        self.rBandLabel = self.MyInfLineLabel(self.rBandSlider, text="{value}",
                                          position=0.5,
                                         anchor=(0, 0.5))
        self.gBandLabel = self.MyInfLineLabel(self.gBandSlider, text="{value}", position=0.5,
                                         anchor=(0, 0.5))
        self.bBandLabel = self.MyInfLineLabel(self.bBandSlider, text="{value}", position=0.5,
                                         anchor=(0, 0.5))

        self.vbox.addItem(self.rBandSlider)
        self.vbox.addItem(self.gBandSlider)
        self.vbox.addItem(self.bBandSlider)

        # Set initial range for the ViewBox
        self.vbox.setRange(xRange=(0, 100), yRange=(-1, 1))  # Adjust as needed

        # Layout setup
        layout = QVBoxLayout()
        layout.addWidget(self.view)
        self.setViewLayout(layout)

    def onBandChanged(self):
        currentBand = self.getBand()
        self.rBandSlider.setValue(currentBand.r)
        self.gBandSlider.setValue(currentBand.g)
        self.bBandSlider.setValue(currentBand.b)

    def onSliderMoved(self):
        if not self.isDragging:
            self.isDragging = True
            self.updateTimer.start(self.updateInterval)  # Update interval in milliseconds

    def updateModel(self):
        self.setBandValues(int(self.rBandSlider.value()),
                           int(self.gBandSlider.value()),
                           int(self.bBandSlider.value())
                           )
        if self.isDragging:
            self.updateTimer.start(self.updateInterval)  # Restart the timer for continuous updates
        self.isDragging = False

    class MyInfLineLabel(pg.InfLineLabel):
        """
        Custom label for InfiniteLine, just so we can round the displayed value to an
        integer
        """
        @override
        def valueChanged(self):
            if not self.isVisible():
                return
            value = int(self.line.value())
            self.setText(self.format.format(value=value))
            self.updatePosition()
