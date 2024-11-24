"""
spectralimageworkspace.py
A QtWidget which acts as a workspace for a single spectral image.
Including a main image display, context image, and zoom image.

NOTE: This is where we'll handle getting the views to interact with each other.
"""
# standard library
import time
from pathlib import Path
from typing import override, overload

# Third-party
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import QThreadPool
import pyqtgraph as pg
import numpy as np
from pyqtgraph.functions import mkPen, Colors
from pyqtgraph import ROI
import cv2
import spectral
import rasterio as rio

# local imports
from . import MenuOverlayWidget, ROIWindow, TripleImageViewer
from models import ImageLoader, AbstractImageModel
from imageprocessing import ImageProcess
import vardathreading
import debug

class ImageWorkspace(QtWidgets.QWidget):
    """
    This class represents an entire "workspace" in varda, which is how the user
    interacts with an image.
    """
    threadpool = QThreadPool()

    class BackgroundWorker(QtCore.QRunnable):
        """
        A basic setup to run functions on a separate thread.
        """

        class Signals(QtCore.QObject):
            """
            QRunnable cannot define pyqtSignals because it doesnt inherit from QObject
            So we create this inner class to define signals
            """
            finished = QtCore.pyqtSignal()
            result = QtCore.pyqtSignal(object)

        def __init__(self, fn, *args, **kwargs):
            """
            Initializes the worker with the function it is to execute when being run
            @param fn: The function we want to run on a seperate thread
            @param args: any necessary function arguments
            @param kwargs: any necessary function keyword arguments
            """
            super().__init__()
            self._fn = fn
            self._args = args
            self._kwargs = kwargs
            self.signals = self.Signals()

        @QtCore.pyqtSlot()
        def run(self):
            result = self._fn(*self._args, **self._kwargs)
            self.signals.result.emit(result)



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
        self.statusBar = WorkspaceStatusBar(self)

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
    def setImageObject(self, image):
        self.onImageLoaded(image)

    def initializeUpdateImageTimer(self):
        self.updateTimer = QtCore.QTimer(self)
        self.updateTimer.setSingleShot(True)
        self.updateTimer.timeout.connect(self.updateContextAndZoom)

    def refreshProcessingMenu(self):
        print("refreshing processing menu")
        print("Image List", AbstractImageModel.subclasses)
        print("Processing List", ImageProcess.subclasses)

        self.processingMenu.clear()
        for process in ImageProcess.subclasses:
            print("process being added to menu:", process)
            self.processingMenu.addAction(process.__name__,
                                          lambda p=process: self.openProcessControlMenu(
                                              p))

    class parameterWidget(QtWidgets.QWidget):
        def __init__(self, process, parent=None):
            super().__init__(parent)

    def openProcessControlMenu(self, process):
        dialog = QtWidgets.QDialog()
        dialog.setWindowTitle(process.name)
        layout = QtWidgets.QFormLayout()
        layout.setSpacing(10)
        dialog.setLayout(layout)

        for name, details in process.parameters.items():
            paramName = QtWidgets.QLabel()
            paramName.setText(name)
            paramName.setToolTip(details["description"])

            if details["type"] == float:
                input = QtWidgets.QLineEdit()
                input.setText(str(details["default"]))
                input.setValidator(QtGui.QDoubleValidator())
                layout.addRow(paramName, input)
            elif details["type"] == bool:
                input = QtWidgets.QCheckBox()
                input.setChecked(details["default"])
                layout.addRow(paramName, input)



        layout.addItem(QtWidgets.QSpacerItem(0, 20,
                                             QtWidgets.QSizePolicy.Policy.Minimum,
                                             QtWidgets.QSizePolicy.Policy.Expanding))
        executeButton = QtWidgets.QPushButton("Execute")
        executeButton.clicked.connect(lambda: self.processImage(
            process))
        layout.addWidget(executeButton)
        layout.addItem(QtWidgets.QSpacerItem(60, 0, QtWidgets.QSizePolicy.Policy.Fixed,
                                             QtWidgets.QSizePolicy.Policy.Minimum))
        dialog.exec()

    def processImage(self, process):
        if self.image is None:
            self.statusBar.showMessage("You must load an image first!", 5000)
            return
        self.statusBar.showLoadingMessage()
        p = process()
        self.appliedProcesses.append(p)
        vardathreading.dispatchThreadProcess(self.image.process, self.onProcessFinished, p)

    def onProcessFinished(self):
        self.statusBar.loadingFinished()

        self.updateImage()

    def dispatchThreadProcess(self, process, onComplete, *args, **kwargs):
        """
        General purpose method to dispatch a process to a thread
        """
        # initialize BackgroundWorker
        worker = self.BackgroundWorker(process, *args, **kwargs)
        # connect signals
        worker.signals.result.connect(onComplete)
        # dispatch thread
        self.threadpool.start(worker)

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
        if (0 <= x < self.image.data.shape[1] and
                0 <= y < self.image.data.shape[0]):

            # Get spectral data for the clicked pixel
            spectral_data = self.image.data[y, x, :]

            # Get wavelength data
            if self.image.meta.wavelength is not None:
                wavelength = self.image.meta.wavelength
            else:
                wavelength = np.arange(self.image.data.shape[2])

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

    @override
    def dragEnterEvent(self, event, **kwargs):
        # dont allow user to load image if previous image is still loading
        if (self.isLoadingImage):
            return
        # TODO: Make it so we don't need to hardcode possible file extensions
        if str(Path(event.mimeData().urls()[0].toLocalFile())).endswith(
                ('.hdr', '.img', '.h5')):
            event.acceptProposedAction()

    @override
    def dropEvent(self, event, **kwargs):
        if self.isLoadingImage:
            self.cancelCurrentLoad()
        if self.image is not None:
            self.image = None
        self.loadImage(str(Path(event.mimeData().urls()[0].toLocalFile())))

    def loadImage(self, fileName):
        self.isLoadingImage = True

        # update status to indicate loading
        self.statusBar.showLoadingMessage()

        # initialize BackgroundWorker
        worker = self.BackgroundWorker(self.createImageObject, fileName)

        # connect signals
        worker.signals.result.connect(self.onImageLoaded)

        # execute thread
        self.threadpool.start(worker)

    def cancelCurrentThread(self):
        self.isLoadingImage = False
        self.threadpool.clear()

    def createImageObject(self, fileName) -> AbstractImageModel:
        return ImageLoader.new_image(fileName)

    def onImageLoaded(self, image):
        self.isLoadingImage = False

        # clear loading status
        self.statusBar.loadingFinished()

        self.image = image
        if self.image.meta.default_bands is not None:
            self.currentBands = self.image.meta.default_bands

        if debug.DEBUG:
            print("image data shape: " + str(self.image.data.shape))

        self.initializePlot()

        self.setImage()
        self.show()

    def initializePlot(self, roi=None):
        timeStarted = time.time()
        self.constructPlot()
        print("time to construct plot: ", time.time() - timeStarted)
        self.onPlotLoaded()

    def constructPlot(self, roi=None):
        if self.image.meta.wavelength is not None:
            wavelength = self.image.meta.wavelength
            if debug.DEBUG:
                print("using wavelength for plot", wavelength)
        else:
            if debug.DEBUG:
                print("using data shape for plot")
                print("data shape: ", self.image.data.shape)
            wavelength = np.arange(self.image.data.shape[2])
        minWavelength = min(wavelength)
        maxWavelength = max(wavelength)

        if self.image.meta.default_bands is not None:
            self.currentBands = self.image.meta.default_bands
        else:
            self.currentBands = {'r': 0, 'g': 0, 'b': 0}

        # construct plot
        if self.plot is None:
            self.plot = pg.plot(x=wavelength, y=self.image.mean,
                                title="Frequency Plot",
                                labels={'left': 'Average Strength',
                                        'bottom': 'Frequency'})
            self.plot.setMouseEnabled(x=False, y=False)
        else:
            self.plot.plotItem.clear()
            self.plot.plotItem.plot(x=wavelength, y=self.image.mean)

        if self.displayGreyscale:
            self.allBandSelect = self.plot.getPlotItem().addLine(
                x=wavelength[self.currentBands['r']],
                pen=(pg.mkPen(color='white', width=2)),
                movable=True,
                bounds=(minWavelength, maxWavelength)
            )
        else:
            self.redBandSelect = self.plot.getPlotItem().addLine(
                x=wavelength[self.currentBands['r']],
                pen=(pg.mkPen(color='red', width=2)),
                movable=True,
                bounds=(minWavelength, maxWavelength)
            )
            self.redBandSelect.sigPositionChanged.connect(self.updateImage)

            self.greenBandSelect = self.plot.getPlotItem().addLine(
                x=wavelength[self.currentBands['g']],
                pen=(pg.mkPen(color='green', width=2)),
                movable=True,
                bounds=(minWavelength, maxWavelength)
            )
            self.greenBandSelect.sigPositionChanged.connect(self.updateImage)

            self.blueBandSelect = self.plot.getPlotItem().addLine(
                x=wavelength[self.currentBands['b']],
                pen=(pg.mkPen(color='blue', width=2)),
                movable=True,
                bounds=(minWavelength, maxWavelength)
            )
            self.blueBandSelect.sigPositionChanged.connect(self.updateImage)

    def onPlotLoaded(self, roi=None):
        # add band selectors to plot
        self.plot.addItem(self.blueBandSelect)
        self.plot.addItem(self.greenBandSelect)
        self.plot.addItem(self.redBandSelect)

        self.mainSplitter.addWidget(self.plot)
        self.mainSplitter.setStretchFactor(2, 4)

    def setImage(self):
        profile = debug.Profiler()
        img = self.image.data[:, :, list(self.currentBands.values())]
        levels = (0, 1)
        axes = {'x': 1, 'y': 0, 'c': 2, 't': None}
        self.imageViewer.setImage(img)

        profile("Time to set images")

    def updateBands(self):
        self.currentBands['r'] = self.bandIndex(self.redBandSelect)
        self.currentBands['g'] = self.bandIndex(self.greenBandSelect)
        self.currentBands['b'] = self.bandIndex(self.blueBandSelect)

    def updateImage(self):
        profile = debug.Profiler()

        self.updateBands()
        img = self.image.data[:, :, list(self.currentBands.values())]
        self.imageViewer.updateImage(img.view())

        # self.updateTimer.start(50)  # Adjust the interval if needed

        profile("time to update main view")

    def updateContextAndZoom(self):
        profile = debug.Profiler()

        img = self.image.data[:, :, list(self.currentBands.values())]
        self.imageViewer.setContextAndZoomImage(img.view())

        profile("time to update context and zoom views")

    def bandIndex(self, band):
        """
        Returns
        -------
        int
            The index of the wavelength closest to the band slider.
        float
            The value of the slider.
        """
        val = band.value()

        if self.image.meta.wavelength is None:
            return int(val)

        inds = np.where(self.image.meta.wavelength <= val)

        if len(inds) < 1:
            return 0
        ind = inds[-1][-1]

        return ind

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

            mean_spec = self.calculate_mean_stats(self.image.data, mask, True)

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


class WorkspaceStatusBar(QtWidgets.QStatusBar):
    """
    A custom widget for the statusbar.
    Lets us create more complex status messages or animations without cluttering the ImageWorkspace class
    """
    def __init__(self, parent=None):
        super(WorkspaceStatusBar, self).__init__(parent)
        self.animationTimer = QtCore.QTimer(self)
        self.animationIndex = None

    def showLoadingMessage(self):
        self.timeStarted = time.time()
        self.animationIndex = 0
        self.animationTimer.timeout.connect(self.updateLoadingMessage)
        self.animationTimer.start(100)  # Update every 100ms

    def updateLoadingMessage(self):
        animationChars = ['-', '\\', '|', '/']
        self.showMessage(f"Loading... {animationChars[self.animationIndex]}")
        self.animationIndex = (self.animationIndex + 1) % len(animationChars)

    def loadingFinished(self):
        if self.animationIndex is None:
            return
        self.timeElapsed = time.time() - self.timeStarted
        self.animationTimer.stop()
        self.animationTimer.timeout.disconnect(self.updateLoadingMessage)
        self.clearMessage()
        # temporary status message
        self.showMessage(self.tr(
            "Image loaded in " + str(round(self.timeElapsed, 2))
            + " seconds"), msecs=5000)
