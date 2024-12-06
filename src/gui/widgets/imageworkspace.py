"""
spectralimageworkspace.py
A QtWidget which acts as a workspace for a single spectral image.
Including a main image display, context image, and zoom image.

NOTE: This is where we'll handle getting the views to interact with each other.
"""
# standard library
import time
import logging

# Third-party
from PyQt6 import QtCore, QtGui, QtWidgets
import pyqtgraph as pg
import numpy as np
from pyqtgraph.functions import mkPen, Colors
import cv2
import spectral

# local imports
from . import ROIWindow
from imageprocessing import ImageProcess
import vardathreading
import debug
from .statusbar import StatusBar

logger = logging.getLogger(__name__)

class ImageWorkspace(QtWidgets.QWidget):
    """
    This class represents an entire "workspace" in varda, which is how the user
    interacts with an image.
    """

    def __init__(self, parent=None, file=None):
        super(ImageWorkspace, self).__init__(parent)
        self.setAcceptDrops(True)
        self.isLoadingImage = False
        self.image = None
        self.plot = None
        self.ROIplot = None
        self.redBandSelect = None
        self.greenBandSelect = None
        self.blueBandSelect = None
        self.allBandSelect = None
        self.displayGreyscale = False
        self.currentROI = None
        self.roiWind = None
        self.sigBandChanged = QtCore.pyqtSignal(int)
        self.updateTimer = None
        self.initializeUpdateImageTimer()
        self.currentBands = {'r': 0, 'g': 0, 'b': 0}
        self.imageAxes = {'x': 1, 'y': 0, 'c': 2, 't': None}
        self.appliedProcesses = []
        self.savedROIs = []
        self.vertices = []
        self.currentROIs = []

        # MenuBar
        self.menuBar = QtWidgets.QMenuBar(self)
        roiMenu = self.menuBar.addMenu("ROI Menu")
        roiInnerMenu = roiMenu.addMenu("ROI Submenu")
        roiInnerMenu.addAction("Option 1")
        roiInnerMenu.addAction("Option 2")

        roiMenu.addAction("Poly ROI", self.addPolylineROI)
        roiMenu.addAction("Save ROI", self.saveROI)
        roiMenu.addAction("Load ROI", self.loadROI)
        self.processingMenu = self.menuBar.addMenu("Processing")
        self.refreshProcessingMenu()

        self.mainSplitter = QtWidgets.QSplitter(
            parent=self, orientation=QtCore.Qt.Orientation.Vertical
        )

        # image views
        self.imageViewer = TripleImageViewer()

        self.mainSplitter.addWidget(self.imageViewer)
        self.mainSplitter.setStretchFactor(0, 30)

        # status bar at bottom
        self.statusBar = StatusBar(self)

        # Create pixel spectrum plot
        self.pixel_plot = pg.PlotWidget(title="Pixel Spectrum")
        self.pixel_plot.setMinimumSize(600, 300)
        self.pixel_plot.setLabels(left='Intensity', bottom='Frequency')
        self.mainSplitter.addWidget(self.pixel_plot)
        self.pixel_plot.hide()
        self.mainSplitter.setStretchFactor(1, 1)

        # Connect mouse click event to the spectral plot update
        self.imageViewer.mainView.scene().sigMouseClicked.connect(
            self.updatePixelPlot)

        # initialize layout
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.menuBar)
        layout.addWidget(self.mainSplitter)
        layout.addWidget(self.statusBar)
        self.setLayout(layout)

        # Load image if file is provided
        if file:
            self.loadImage(file)

    def updatePixelPlot(self, event):
        print(event.scenePos())
        """
        Update the pixel spectrum plot with data from the clicked pixel 
        """
        if self.image is None:
            return

        # Get click position in image coordinates
        pos = self.imageViewer.mainImageItem.mapFromScene(event.scenePos())
        x, y = int(pos.x()), int(pos.y())

        # Check if click is within image bounds
        if (0 <= x < self.image.rasterData.shape[1] and
                0 <= y < self.image.rasterData.shape[0]):

            # Get spectral data for the clicked pixel
            spectral_data = self.image.rasterData[y, x, :]

            # Get wavelength data
            if self.image.meta.wavelength is not None:
                wavelength = self.image.meta.wavelength
            else:
                wavelength = np.arange(self.image.rasterData.shape[2])

            # Clear previous plot and create new one
            self.pixel_plot.clear()
            self.pixel_plot.plot(wavelength, spectral_data, pen='y')

            # Update plot title with pixel coordinates
            self.pixel_plot.setTitle(f"Pixel Spectrum at ({x}, {y})")

            # Update status bar
            self.statusBar.showMessage(
                f"Selected pixel coordinates: ({x}, {y})",
                msecs=3000
            )

    def loadROI(self):
        if self.roiWind:
            self.roiWind.updateROIs(self.savedROIs)
        self.roiWind = ROIWindow(self, self.savedROIs)
        self.roiWind.show()

    def showProcessingMenu(self):
        self.processingMenu.exec(
            self.options.mapToGlobal(self.options.rect().bottomLeft()))

    def loadROIState(self, i):
        self.currentROI = self.savedROIs[i]

    def saveROI(self):
        if self.currentROI is not None:
            if self.currentROI not in self.savedROIs:
                self.savedROIs.append(self.currentROI)
            else:
                update_curr = self.savedROIs.index(self.currentROI)
                self.savedROIs[update_curr].setState(self.currentROI.getState())

    def addPolylineROI(self):
        color_keys = ['b', 'g', 'r', 'c', 'm', 'y', 'w']
        if self.currentROI is not None and self.currentROI not in self.savedROIs:
            self.savedROIs.append(self.currentROI)
        initial_points = [[100, 100], [100, 300], [300, 300], [300, 100]]
        self.currentROI = pg.PolyLineROI(initial_points, closed=True)
        self.currentROI.setPen(mkPen(cosmetic=False, width=2,
                                     color=Colors[color_keys[len(self.currentROIs)]]))
        self.currentROIs.append(self.currentROI)
        for ROI in self.currentROIs:
            self.imageViewer.mainView.addItem(ROI)

    def roi_in_range(self, roi):
        # checking to see if the roi is fully inside the image. Not sure if this is
        # necessary, or if rois can be slightly outside the image and thats okay
        if self.image:
            img_width, img_height = self.image._meta.width, self.image._meta.height

            for vertex in roi.getLocalHandlePositions():
                pos = vertex[1]
                x, y = pos.x(), pos.y()

                if 0 <= x < img_width and 0 <= y < img_height:
                    return True

            print("ROI is not fully contained inside the image")
        print("No image has been loaded yet")
        return False

    def calculate_mean_stats(self, data, mask, allow_nan):
        gstats = spectral.calc_stats(data, mask=mask, allow_nan=allow_nan)
        mean_spectrum = gstats.mean
        mean_spectrum = np.where(mean_spectrum < 0, np.nan, mean_spectrum)
        mean_spectrum = np.where(mean_spectrum > 1, np.nan, mean_spectrum)
        return mean_spectrum

    def calculate_std_stats(self, data, mask, allow_nan):
        # mask_std = np.zeros((self.image._meta.height, self.image._meta.width, self.image._meta.bandcount), dtype=np.uint8)
        # std_spectrum = data * mask_std
        # std_spectrum = np.where(mask_std < 0, np.nan, mask_std)
        # std_spectrum = np.where(mask_std > 1, np.nan, mask_std)
        # std_spectrum = np.nanstd(std_spectrum)

        # todo: figure out how to calculate std stats
        gstats = spectral.calc_stats(data, mask=mask, allow_nan=allow_nan)
        mean_spectrum = gstats.mean
        mean_spectrum = np.where(mean_spectrum < 0, np.nan, mean_spectrum)
        mean_spectrum = np.where(mean_spectrum > 1, np.nan, mean_spectrum)
        return mean_spectrum

    def loadMeanPlot(self, roi):
        print("Loading mean spectrum plot...")
        if (self.roi_in_range(roi)):
            # (Using similar routine to original scat.py), getting the roi as a slice of the
            # data image array, then masking it with the original image
            # Need to check with michael that this is done correctly
            mask = np.zeros((self.image._meta.width, self.image._meta.height),
                            dtype=np.uint8)

            polygon_points_int = [(int(pos.x()), int(pos.y())) for _, pos in
                                  roi.getLocalHandlePositions()]
            cv2.fillPoly(mask, [np.array(polygon_points_int)], 1)

            mean_spec = self.calculate_mean_stats(self.image.rasterData, mask, True)

            print("plotting spectrum ")
            #if self.plot is None:
            self.ROIplot = pg.plot(x=range(len(mean_spec)), y=mean_spec,
                                title="Mean spectrum",
                                labels={'left': 'Average Strength',
                                        'bottom': 'Band'})
            self.ROIplot.setMouseEnabled(x=False, y=False)
            self.ROIplot.setMinimumSize(600, 300)
            self.ROIplot.setMaximumSize(1100, 300)
            self.plot.hide()
            self.mainSplitter.addWidget(self.ROIplot)

    def loadStdPlot(self, roi):
        print("Loading std spectrum plot...")
        if (self.roi_in_range(roi)):
            # (Using similar routine to original scat.py), getting the roi as a slice of the
            # data image array, then masking it with the original image
            # Need to check with michael that this is done correctly
            mask1 = np.zeros((self.image._meta.width, self.image._meta.height),
                             dtype=np.uint8)

            polygon_points_int = [(int(pos.x()), int(pos.y())) for _, pos in
                                  roi.getLocalHandlePositions()]
            cv2.fillPoly(mask1, [np.array(polygon_points_int)], 1)

            std_spec = self.calculate_std_stats(self.image._data, mask1, True)

            print("plotting spectrum (std)")
            bands = self.image._meta.bandcount
            # if self.plot is None:
            #     self.plot = pg.plot(x=range(len(std_spec)), y=std_spec,
            #                         title="Mean spectrum",
            #                         labels={'left': 'Average Strength',
            #                                 'bottom': 'Band'})
            #     self.plot.setMouseEnabled(x=False, y=False)
            # else:
            #     self.plot.plotItem.clear()
            #     self.plot.setWindowTitle("Mean spectrum")
            #     self.plot.setLabel('bottom', "Band")
            #     self.plot.setLabel('left', "Average Strength")
            #     self.plot.plot(range(len(std_spec)), std_spec)

            self.ROIplot = pg.plot(x=range(len(std_spec)), y=std_spec,
                                title="Mean spectrum",
                                labels={'left': 'Average Strength',
                                        'bottom': 'Band'})
            self.ROIplot.setMouseEnabled(x=False, y=False)
            self.ROIplot.setMinimumSize(600, 300)
            self.ROIplot.setMaximumSize(1100, 300)
            self.plot.hide()
            self.mainSplitter.addWidget(self.ROIplot)
