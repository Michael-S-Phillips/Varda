"""
spectralimagedisplay.py
"""
from typing import override

from PyQt6 import QtCore, QtGui, QtWidgets
import pyqtgraph as pg
from pyqtgraph import ImageView, InfiniteLine


class SpectralMainImageDisplay(ImageView):

    def __init__(self, parent=None):
        super(SpectralMainImageDisplay, self).__init__(parent)
        pg.setConfigOptions(imageAxisOrder='row-major')
        self.getImageItem().setLevels(None, None)
        self.setAcceptDrops(True)

        self.buttonLayout = None
        self.currentROI = None
        self.vertices = []

        self.currentBands = [9, 19, 29]

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

        self.red_band_select = InfiniteLine(50, movable=True)
        self.red_band_select.setPen(color='r', width=2)
        self.red_band_select.setZValue(1)
        self.ui.roiPlot.addItem(self.red_band_select)
        self.red_band_select.show()

        self.green_band_select = InfiniteLine(100, movable=True)
        self.green_band_select.setPen(color='g', width=2)
        self.green_band_select.setZValue(1)
        self.ui.roiPlot.addItem(self.green_band_select)
        self.green_band_select.show()

        self.blue_band_select = InfiniteLine(150, movable=True)
        self.blue_band_select.setPen(color='blue', width=2)
        self.blue_band_select.setZValue(1)
        self.ui.roiPlot.addItem(self.blue_band_select)
        self.blue_band_select.show()


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
    def updateImage(self, autoHistogramRange=True):
        ## Redraw image on screen
        if self.image is None:
            return

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
            image = image[:, :, self.currentBands]
        self.imageItem.updateImage(image)

    def setRedIndex(self, ind):
        self.currentBands[0] = ind

    def setCurrentIndex(self, ind):
        """Set the currently displayed frame index."""
        index = pg.fn.clip_scalar(ind, 0, self.nframes()-1)
        self.currentIndex = index
        self.updateImage()
        self.ignoreTimeLine = True
        # Implicitly call timeLineChanged
        self.timeLine.setValue(self.tVals[index])
        self.ignoreTimeLine = False

class SpectralZoomImage(ImageView):
    def __init__(self, parent):
        super(SpectralZoomImage, self).__init__(parent)
        self.ui.histogram.hide()


class SpectralContextImage(ImageView):
    def __init__(self, parent):
        super(SpectralContextImage, self).__init__(parent)
        self.ui.histogram.hide()
