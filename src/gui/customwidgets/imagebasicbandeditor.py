
# standard library
from typing import override

# third-party imports
import pyqtgraph as pg
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QLineEdit, QHBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal

# local imports
from gui.customwidgets.BaseImageView import BaseImageView


class ImageBasicBandEditor(BaseImageView):

    widgetHeight = 152

    def __init__(self, imageModel=None, parent=None):
        super().__init__(imageModel, parent)
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

        self.setMaximumHeight(self.widgetHeight)
        
        self.show()

    def setModel(self, image):
        self.imageModel = image
        self.imageModel.bandsChanged.connect(self.updateView)
        self.vbox.setRange(xRange=(0, self.imageModel.bandCount - 1))
        self.updateView()

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

        self.rBandSlider.sigPositionChanged.connect(self.updateModel)
        self.gBandSlider.sigPositionChanged.connect(self.updateModel)
        self.bBandSlider.sigPositionChanged.connect(self.updateModel)

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
        self.setLayout(layout)

        # Initial positions for sliders
        self.rBandSlider.setValue(25)
        self.gBandSlider.setValue(50)
        self.bBandSlider.setValue(75)

    def updateView(self):
        self.rBandSlider.setValue(self.imageModel.band['r'])
        self.gBandSlider.setValue(self.imageModel.band['g'])
        self.bBandSlider.setValue(self.imageModel.band['b'])

    def updateModel(self):
        self.imageModel.band = {'r': self.rBandSlider.value(),
                                'g': self.gBandSlider.value(),
                                'b': self.bBandSlider.value()}

    class MyInfLineLabel(pg.InfLineLabel):
        @override
        def valueChanged(self):
            if not self.isVisible():
                return
            value = int(self.line.value())
            self.setText(self.format.format(value=value))
            self.updatePosition()
