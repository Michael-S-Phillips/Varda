"""
spectralimagedisplay.py
"""
from typing import override

from PyQt6 import QtCore, QtGui, QtWidgets
import pyqtgraph as pg
from pyqtgraph import ImageView, InfiniteLine
from pyqtgraph import functions as fn


class SpectralMainImageDisplay(ImageView):

    def __init__(self, parent=None):
        super(SpectralMainImageDisplay, self).__init__(parent)
        self.ui.histogram.setLevelMode("rgba")
        pg.setConfigOptions(imageAxisOrder='row-major')
        self.setAcceptDrops(True)

        self.buttonLayout = None
        self.currentROI = None
        self.vertices = []

        self.currentBands = {'r': 9, 'g': 19, 'b': 29}

        self.buttonLayout = QtWidgets.QHBoxLayout()
        self.currentROI = None

        self.polylineROIButton = QtWidgets.QPushButton("Poly ROI", self)
        self.polylineROIButton.clicked.connect(self.addPolylineROI)
        self.polylineROIButton.setStyleSheet("""
            QPushButton {
                background-color: white;
                width: 80px;
                height: 20px;
                color: black;
                font-size: 10px;
                border-radius: 5px;
                border: 1px solid black;

            }
            QPushButton:hover {
                background-color: lightgray;
            }
        """)
        self.buttonLayout.addWidget(self.polylineROIButton)

        self.redBandSelect = InfiniteLine(50, movable=True)
        self.redBandSelect.setPen(color='r', width=2)
        self.redBandSelect.setZValue(1)
        self.ui.roiPlot.addItem(self.redBandSelect)
        self.redBandSelect.show()
        self.redBandSelect.sigPositionChanged.connect(self.redBandChanged)

        self.greenBandSelect = InfiniteLine(100, movable=True)
        self.greenBandSelect.setPen(color='g', width=2)
        self.greenBandSelect.setZValue(1)
        self.ui.roiPlot.addItem(self.greenBandSelect)
        self.greenBandSelect.show()
        self.greenBandSelect.sigPositionChanged.connect(self.greenBandChanged)

        self.blueBandSelect = InfiniteLine(150, movable=True)
        self.blueBandSelect.setPen(color='blue', width=2)
        self.blueBandSelect.setZValue(1)
        self.ui.roiPlot.addItem(self.blueBandSelect)
        self.blueBandSelect.show()
        self.blueBandSelect.sigPositionChanged.connect(self.blueBandChanged)

    def addRectangularROI(self):
        if self.currentROI is not None:
            self.removeItem(self.currentROI)

        self.currentROI = pg.RectROI([100, 100], [100, 100], pen=(10, 9, 100))
        self.currentROI.sigRegionChanged.connect(self.updateROI)
        self.addItem(self.currentROI)

    def addPolylineROI(self):
        if self.currentROI is not None:
            self.removeItem(self.currentROI)

        initial_points = [[100, 100], [100, 300], [300, 300], [300, 100]]
        self.currentROI = pg.PolyLineROI(initial_points, closed=True, pen=(10, 15, 10))
        self.currentROI.sigRegionChanged.connect(self.updateROI)
        self.addItem(self.currentROI)

    def updateROI(self):
        if isinstance(self.currentROI, pg.PolyLineROI):
            print(f"Polyline ROI points: {self.currentROI.getState()['points']}")

    """
    we override this method to allow for refreshing the image with custom bands 
    without re-running the entire setImage method (laggy)
    """

    @override
    def updateImage(self, autoHistogramRange=False):
        ## Redraw image on screen
        if self.image is None:
            return
        print(self.currentBands)

        image = self.getProcessedImage()
        if autoHistogramRange:
            self.ui.histogram.setHistogramRange(self.levelMin, self.levelMax)

        # Transpose image into order expected by ImageItem
        if self.imageItem.axisOrder == 'col-major':
            axorder = ['x', 'y', 't', 'c']
        else:
            axorder = ['y', 'x', 't', 'c']
        print(axorder)
        axorder = [self.axes[ax] for ax in axorder if self.axes[ax] is not None]
        print(axorder)

        print(image.shape)
        image = image.transpose(axorder)
        print(image.shape)

        # Select time index
        if self.axes['t'] is not None:
            self.ui.roiPlot.show()
            image = image[:, :, list(self.currentBands.values())]
        self.imageItem.updateImage(image)

    def setRedIndex(self, ind):
        """Set the currently displayed frame index."""
        index = fn.clip_scalar(ind, 0, self.nframes() - 1)
        self.currentIndex = index
        self.updateImage()
        self.ignoreTimeLine = True
        # Implicitly call timeLineChanged
        self.redBandSelect.setValue(self.tVals[index][0])
        self.ignoreTimeLine = False

    def setGreenIndex(self, ind):
        """Set the currently displayed frame index."""
        index = fn.clip_scalar(ind, 0, self.nframes() - 1)
        self.currentIndex = index
        self.updateImage()
        self.ignoreTimeLine = True
        # Implicitly call timeLineChanged
        self.greenBandSelect.setValue(self.tVals[index][1])
        self.ignoreTimeLine = False

    def setBlueIndex(self, ind):
        """Set the currently displayed frame index."""
        index = fn.clip_scalar(ind, 0, self.nframes() - 1)
        self.currentIndex = index
        self.updateImage()
        self.ignoreTimeLine = True
        # Implicitly call timeLineChanged
        self.blueBandSelect.setValue(self.tVals[index][2])
        self.ignoreTimeLine = False

    def redBandChanged(self):
        (ind, time) = self.timeIndex(self.redBandSelect)
        if ind != self.currentBands['r']:
            self.currentBands['r'] = ind
            self.updateImage()

        # if self.discreteTimeLine:
        #     with fn.SignalBlock(self.timeLine.sigPositionChanged, self.timeLineChanged):
        #         if self.tVals is not None:
        #             self.timeLine.setPos(self.tVals[ind])
        #         else:
        #             self.timeLine.setPos(ind)

        self.sigTimeChanged.emit(ind, time)

    def greenBandChanged(self):
        (ind, time) = self.timeIndex(self.greenBandSelect)
        if ind != self.currentBands['g']:
            self.currentBands['g'] = ind
            self.updateImage()

        # if self.discreteTimeLine:
        #     with fn.SignalBlock(self.timeLine.sigPositionChanged, self.timeLineChanged):
        #         if self.tVals is not None:
        #             self.timeLine.setPos(self.tVals[ind])
        #         else:
        #             self.timeLine.setPos(ind)

        self.sigTimeChanged.emit(ind, time)

    def blueBandChanged(self):
        (ind, time) = self.timeIndex(self.blueBandSelect)
        if ind != self.currentBands['b']:
            self.currentBands['b'] = ind
            self.updateImage()

        # if self.discreteTimeLine:
        #     with fn.SignalBlock(self.timeLine.sigPositionChanged, self.timeLineChanged):
        #         if self.tVals is not None:
        #             self.timeLine.setPos(self.tVals[ind])
        #         else:
        #             self.timeLine.setPos(ind)

        self.sigTimeChanged.emit(ind, time)


class SpectralZoomImage(ImageView):
    def __init__(self, parent):
        super(SpectralZoomImage, self).__init__(parent)
        self.ui.histogram.hide()


class SpectralContextImage(ImageView):
    def __init__(self, parent):
        super(SpectralContextImage, self).__init__(parent)
        self.ui.histogram.hide()
