"""
spectralimageworkspace.py
A QtWidget which acts as a workspace for a single spectral image.
Including a main image display, context image, and zoom image.

NOTE: This is where we'll handle getting the views to interact with each other.
"""
# standard library
import time
from pathlib import Path
from typing import override

# Third-party
from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtCore import QThreadPool
import pyqtgraph as pg
import numpy as np

# local imports
from speclabgui.customwidgets.spectralimagedisplays import (
    SpectralMainImageDisplay,
    SpectralZoomImage,
    SpectralContextImage)
import speclabimageprocessing as speclab
from speclabimageprocessing import ImageLoader
from vardaconfig import DEBUG


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

        self.isLoadingImage = False
        self.image = None
        self.plot = None
        self.redBandSelect = None
        self.greenBandSelect = None
        self.blueBandSelect = None
        self.sigBandChanged = QtCore.pyqtSignal(int)
        self.currentBands = {'r': 0, 'g': 0, 'b': 0}

        # create main layout
        layout = QtWidgets.QVBoxLayout()
        self.mainSplitter = QtWidgets.QSplitter(self)

        self.mainImage = SpectralMainImageDisplay(parent)
        self.contextImage = SpectralContextImage(parent)
        self.zoomImage = SpectralZoomImage(parent)
        self.contextZoomSplitter = QtWidgets.QSplitter(self)
        self.contextZoomSplitter.addWidget(self.contextImage)
        self.contextZoomSplitter.addWidget(self.zoomImage)

        self.mainSplitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.mainSplitter.addWidget(self.mainImage)
        self.mainSplitter.addWidget(self.contextZoomSplitter)

        layout.addWidget(self.mainSplitter)

        # initialize status bar at bottom of widget
        self.statusBar = WorkspaceStatusBar(self)
        layout.addWidget(self.statusBar)

        self.setLayout(layout)

    @override
    def dragEnterEvent(self, event, **kwargs):
        # TODO: Allow other file extensions
        # dont allow user to load image if previous image is still loading
        if (self.isLoadingImage):
            return
        event.acceptProposedAction()

    @override
    def dropEvent(self, event, **kwargs):
        self.loadImage(str(Path(event.mimeData().urls()[0].toLocalFile())))

    def loadImage(self, fileName):
        self.isLoadingImage = True

        img = ImageLoader()
        # update status to indicate loading
        self.statusBar.showLoadingMessage()

        # initialize BackgroundWorker
        worker = self.BackgroundWorker(self.actuallyLoadImage, fileName)

        # connect signals
        worker.signals.result.connect(self.onImageLoaded)
        # self.thread.started.connect(self.worker.loadImage)

        # execute thread
        self.threadpool.start(worker)
        # self.thread.start()

    def actuallyLoadImage(self, fileName):
        return speclab.ImageLoader.new_image(fileName)

    def onImageLoaded(self, image):
        self.isLoadingImage = False

        # clear loading status
        self.statusBar.clearLoadingMessage()

        # temporary status message
        self.statusBar.showMessage(self.statusBar.tr(
            "Image loaded in " + str(round(self.statusBar.timeElapsed, 2))
            + " seconds"), msecs=5000)
        self.image = image
        self.currentBands = self.image.meta["default bands"]

        if DEBUG:
            print("image data shape: " + str(self.image.data.shape))

        self.initializePlot()

        img = self.image.data[:, :, list(self.currentBands.values())].data
        levels = (0, 1)
        axes = {'x': 1, 'y': 0, 'c': 2, 't': None}
        self.mainImage.setImage(img, autoLevels=False, levels=levels, axes=axes,
                                autoHistogramRange=False)
        self.contextImage.setImage(img, autoLevels=False, levels=levels, axes=axes,
                                   autoHistogramRange=False)
        self.zoomImage.setImage(img, autoLevels=False, levels=levels, axes=axes,
                                autoHistogramRange=False)

        self.updateImage()
        self.show()

    def initializePlot(self):
        timeStarted = time.time()
        self.constructPlot()
        print("time to construct plot: ", time.time() - timeStarted)
        self.onPlotLoaded()

    def constructPlot(self):
        if self.image.meta["wavelength"] is not None:
            wavelength = self.image.meta["wavelength"]
        elif self.image.meta["bands"] is not None:
            wavelength = np.arange(self.image.meta["bands"])
        else:
            wavelength = self.image.data.shape[2]
        minWavelength = min(wavelength)
        maxWavelength = max(wavelength)

        # construct plot
        if self.plot is None:
            self.plot = pg.plot(x=wavelength, y=self.image.mean,
                                title="Frequency Plot",
                                labels={'left': 'Average Strength',
                                        'bottom': 'Frequency'})
            self.plot.setMouseEnabled(x=False, y=False)
        else:
            self.plot.plotItem.clear()
            self.plot.plotItem.plot(self.image.mean)

        # construct red band selector
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

        # construct green band selector
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

        # construct blue band selector
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

    def onPlotLoaded(self):
        # add band selectors to plot
        self.plot.addItem(self.blueBandSelect)
        self.plot.addItem(self.greenBandSelect)
        self.plot.addItem(self.redBandSelect)

        self.mainSplitter.addWidget(self.plot)

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

    def updateImage(self):
        img = self.image.data[:, :, list(self.currentBands.values())].data
        # timeStart = time.time()
        self.mainImage.updateImage(img)
        # print("Time to set Image: ", time.time() - timeStart)

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

        if self.image.meta["wavelength"] is None:
            return int(val), val

        inds = np.where(self.image.meta["wavelength"] <= val)

        if len(inds) < 1:
            return 0, val

        ind = inds[-1][-1]

        return ind, val


"""
A custom widget for the statusbar. 
Lets us create more complex status messages or animations without cluttering the ImageWorkspace class
"""


class WorkspaceStatusBar(QtWidgets.QStatusBar):
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

    def clearLoadingMessage(self):
        self.timeElapsed = time.time() - self.timeStarted
        self.animationTimer.stop()
        self.animationTimer.timeout.disconnect(self.updateLoadingMessage)
        self.clearMessage()
