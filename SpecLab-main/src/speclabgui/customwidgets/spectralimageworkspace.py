"""
spectralimageworkspace.py
A QtWidget which acts as a workspace for a single spectral image.
Including a main image display, context image, zoom image, and spectral plots.
"""
# standard library
import time
from pathlib import Path
from typing import override
import cProfile

# Third-party
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import QThreadPool
import pyqtgraph as pg
import numpy as np
from pyqtgraph.functions import mkPen, Colors

# local imports
import speclabimageprocessing as speclab
from speclabimageprocessing import ImageLoader, Image
from . import ROIWindow
import debug


class SpectralImageWorkspace(QtWidgets.QWidget):
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

    def __init__(self, parent=None):
        super(SpectralImageWorkspace, self).__init__(parent)
        self.setAcceptDrops(True)

        self.update_timer = QtCore.QTimer()
        self.update_timer = QtCore.QTimer(self)
        self.update_timer.setSingleShot(True)
        self.update_timer.timeout.connect(self.updateContextAndZoom)

        self.isLoadingImage = False
        self.image = None
        self.mean_plot = None  # Plot for average spectrum
        self.pixel_plot = None  # Plot for pixel spectrum
        self.redBandSelect = None
        self.greenBandSelect = None
        self.blueBandSelect = None
        self.sigBandChanged = QtCore.pyqtSignal(int)
        self.currentBands = {'r': 0, 'g': 0, 'b': 0}

        self.currentROI = None
        self.savedROIs = []
        self.vertices = []
        self.currentROIs = []

        # create main layout
        layout = QtWidgets.QVBoxLayout()
        self.mainSplitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)

        # Create top section for images
        self.imageSplitter = QtWidgets.QSplitter(self)

        self.mainImage = pg.ImageView(parent)
        self.contextImage = pg.ImageView(parent)
        self.zoomImage = pg.ImageView(parent)
        self.contextImage.ui.histogram.hide()
        self.zoomImage.ui.histogram.hide()

        # Connect mouse click event to the spectral plot update
        self.mainImage.scene.sigMouseClicked.connect(self.updatePixelPlot)

        self.contextZoomSplitter = QtWidgets.QSplitter(self)
        self.contextZoomSplitter.addWidget(self.contextImage)
        self.contextZoomSplitter.addWidget(self.zoomImage)

        # Options button and menu
        self.options = QtWidgets.QPushButton("Options", self)
        self.options.clicked.connect(self.showMenu)

        self.menuButton = QtWidgets.QMenu(self)
        self.menuButton.addAction("Poly ROI", self.addPolylineROI)
        self.menuButton.addAction("Save ROI", self.saveROI)
        self.menuButton.addAction("Load ROI", self.loadROI)

        # Add widgets to main splitter
        self.mainSplitter.addWidget(self.options)
        self.mainSplitter.addWidget(self.mainImage)
        self.mainSplitter.addWidget(self.contextZoomSplitter)

        # Create plots
        self.mean_plot = pg.PlotWidget(title="Average Spectrum")
        self.mean_plot.setLabels(left='Average Strength', bottom='Frequency')
        self.pixel_plot = pg.PlotWidget(title="Pixel Spectrum")
        self.pixel_plot.setLabels(left='Intensity', bottom='Frequency')

        # Add plots to splitter
        self.mainSplitter.addWidget(self.mean_plot)
        self.mainSplitter.addWidget(self.pixel_plot)

        layout.addWidget(self.mainSplitter)

        # initialize status bar at bottom of widget
        self.statusBar = WorkspaceStatusBar(self)
        layout.addWidget(self.statusBar)

        self.setLayout(layout)

    @override
    def dragEnterEvent(self, event, **kwargs):
        if (self.isLoadingImage):
            return
        event.acceptProposedAction()

    @override
    def dropEvent(self, event, **kwargs):
        self.loadImage(str(Path(event.mimeData().urls()[0].toLocalFile())))

    def loadImage(self, fileName):
        self.isLoadingImage = True
        self.statusBar.showLoadingMessage()
        worker = self.BackgroundWorker(self.createImageObject, fileName)
        worker.signals.result.connect(self.onImageLoaded)
        self.threadpool.start(worker)

    def createImageObject(self, fileName) -> Image:
        return speclab.ImageLoader.new_image(fileName)

    def onImageLoaded(self, image):
        self.isLoadingImage = False
        self.statusBar.clearLoadingMessage()
        self.statusBar.showMessage(self.statusBar.tr(
            "Image loaded in " + str(round(self.statusBar.timeElapsed, 2))
            + " seconds"), msecs=5000)
        self.image = image
        if self.image.meta.default_bands is not None:
            self.currentBands = self.image.meta.default_bands

        if debug.DEBUG:
            print("image data shape: " + str(self.image.data.shape))

        self.initializePlot()
        self.setImage()
        self.show()

    def initializePlot(self):
        timeStarted = time.time()
        self.constructPlot()
        print("time to construct plot: ", time.time() - timeStarted)

    def updatePixelPlot(self, event):
        """
        Update the pixel spectrum plot with data from the clicked pixel
        """
        if self.image is None:
            return

        # Get click position in image coordinates
        pos = self.mainImage.getImageItem().mapFromScene(event.scenePos())
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

    def constructPlot(self):
        if self.image.meta.wavelength is not None:
            wavelength = self.image.meta.wavelength
            if debug.DEBUG:
                print("using wavelength for plot")
        else:
            if debug.DEBUG:
                print("using data shape for plot")
                print("data shape: ", self.image.data.shape)
            wavelength = np.arange(self.image.data.shape[2])
        minWavelength = min(wavelength)
        maxWavelength = max(wavelength)

        # Clear and update mean spectrum plot
        self.mean_plot.clear()
        self.mean_plot.plot(wavelength, self.image.mean, pen='w')

        # Add band selectors to mean plot
        if self.redBandSelect is None:
            self.redBandSelect = pg.InfiniteLine(
                pos=wavelength[self.image.default_bands['r']],
                pen=(pg.mkPen(color='red', width=2)),
                movable=True,
                bounds=(minWavelength, maxWavelength)
            )
            self.redBandSelect.sigPositionChanged.connect(self.redBandChanged)
        else:
            self.redBandSelect.setBounds((minWavelength, maxWavelength))

        if self.greenBandSelect is None:
            self.greenBandSelect = pg.InfiniteLine(
                pos=wavelength[self.image.default_bands['g']],
                pen=(pg.mkPen(color='green', width=2)),
                movable=True,
                bounds=(minWavelength, maxWavelength)
            )
            self.greenBandSelect.sigPositionChanged.connect(self.greenBandChanged)
        else:
            self.greenBandSelect.setBounds((minWavelength, maxWavelength))

        if self.blueBandSelect is None:
            self.blueBandSelect = pg.InfiniteLine(
                pos=wavelength[self.image.default_bands['b']],
                pen=(pg.mkPen(color='blue', width=2)),
                movable=True,
                bounds=(minWavelength, maxWavelength)
            )
            self.blueBandSelect.sigPositionChanged.connect(self.blueBandChanged)
        else:
            self.blueBandSelect.setBounds((minWavelength, maxWavelength))

        # Add band selectors to plot
        self.mean_plot.addItem(self.redBandSelect)
        self.mean_plot.addItem(self.greenBandSelect)
        self.mean_plot.addItem(self.blueBandSelect)

    def redBandChanged(self):
        (ind, val) = self.bandIndex(self.redBandSelect)
        if ind != self.currentBands['r']:
            self.currentBands['r'] = ind
            self.updateImage()

    def greenBandChanged(self):
        (ind, val) = self.bandIndex(self.greenBandSelect)
        if ind != self.currentBands['g']:
            self.currentBands['g'] = ind
            self.updateImage()

    def blueBandChanged(self):
        (ind, val) = self.bandIndex(self.blueBandSelect)
        if ind != self.currentBands['b']:
            self.currentBands['b'] = ind
            self.updateImage()

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
            return int(val), val

        inds = np.where(self.image.meta.wavelength <= val)

        if len(inds) < 1:
            return 0, val

        ind = inds[-1][-1]

        return ind, val

    def setImage(self):
        if debug.DEBUG:
            timeStarted = time.perf_counter() * 1000
        img = self.image.data[:, :, list(self.currentBands.values())]
        levels = (0, 1)
        axes = {'x': 1, 'y': 0, 'c': 2, 't': None}

        self.mainImage.setImage(img, autoLevels=False, levels=levels,
                                axes=axes, autoHistogramRange=False, levelMode="rgba")
        self.contextImage.setImage(img, autoLevels=False, levels=levels,
                                   axes=axes, autoHistogramRange=False, levelMode="rgba")
        self.zoomImage.setImage(img, autoLevels=False, levels=levels,
                                axes=axes, autoHistogramRange=False, levelMode="rgba")

        if timeStarted:
            print("time to set images:", round(time.perf_counter() * 1000 -
                                               timeStarted, 3), "ms")

    def updateImage(self):
        profile = debug.Profiler()
        img = self.image.data[:, :, list(self.currentBands.values())]

        self.mainImage.imageItem.image = img.view()
        self.mainImage.imageItem.updateImage()

        self.update_timer.start(50)
        profile("time to update views")

    def updateContextAndZoom(self):
        img = self.image.data[:, :, list(self.currentBands.values())]

        self.contextImage.imageItem.image = img.view()
        self.contextImage.imageItem.updateImage()

        self.zoomImage.imageItem.image = img.view()
        self.zoomImage.imageItem.updateImage()

    def loadROI(self):
        roiPopupWindow = ROIWindow(self.mainImage, self.savedROIs)
        roiPopupWindow.show()

    def showMenu(self):
        self.menuButton.exec(self.options.mapToGlobal(self.options.rect().bottomLeft()))

    def loadROIState(self, i):
        self.currentROI.setState(self.savedROIs[i])

    def saveROI(self):
        if (self.currentROI != None):
            state = self.currentROI.saveState()
            self.savedROIs.append(state)

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
            self.mainImage.addItem(ROI)

class WorkspaceStatusBar(QtWidgets.QStatusBar):
    def __init__(self, parent=None):
        super(WorkspaceStatusBar, self).__init__(parent)
        self.animationTimer = QtCore.QTimer(self)
        self.animationIndex = None
        self.timeStarted = None
        self.timeElapsed = None

    def showLoadingMessage(self):
        self.timeStarted = time.time()
        self.animationIndex = 0
        self.animationTimer.timeout.connect(self.updateLoadingMessage)
        self.animationTimer.start(100)  # Update every 100ms

    def updateLoadingMessage(self):
        animationChars = ['-', '\\', '|', '/']
        self.showMessage(f"Loading... {animationChars[self.animationIndex]}")
        self.animationIndex = (self.animationIndex + 1) % len(animationChars)

    def clearLoadingMessage(self):
        self.timeElapsed = time.time() - self.timeStarted
        self.animationTimer.stop()
        self.animationTimer.timeout.disconnect(self.updateLoadingMessage)
        self.clearMessage()