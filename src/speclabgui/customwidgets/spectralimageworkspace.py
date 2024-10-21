"""
spectralimageworkspace.py
A QtWidget which acts as a workspace for a single spectral image.
Including a main image display, context image, and zoom image.

NOTE: This is where we'll handle getting the views to interact with each other.
"""
import time
from pathlib import Path
from typing import override

import numpy as np
from PyQt6 import QtCore, QtGui, QtWidgets
from pyqtgraph.functions import mkPen, Colors
from pyqtgraph import InfiniteLine, ImageView
from PyQt6.QtWidgets import QMenu
from speclabgui.customwidgets.ROIWindow import ROIWindow

import speclabimageprocessing as speclab
import pyqtgraph as pg


class SpectralImageWorkspace(QtWidgets.QWidget):

    def __init__(self, parent=None):
        super(SpectralImageWorkspace, self).__init__(parent)
        self.setAcceptDrops(True)

        self.sdv = None
        self.plot = None
        self.redBandSelect = None
        self.greenBandSelect = None
        self.blueBandSelect = None
        self.sigBandChanged = QtCore.pyqtSignal(int)
        self.currentBands = {'r': 0, 'g': 0, 'b': 0}

        self.currentROI = None
        self.savedROIs = []
        self.vertices = []
        self.currentROIs = []

        layout = QtWidgets.QVBoxLayout()
        self.mainSplitter = QtWidgets.QSplitter(self)

        self.mainImage = ImageView(parent)
        self.contextImage = ImageView(parent)
        self.zoomImage = ImageView(parent)
        self.contextImage.ui.histogram.hide()
        self.zoomImage.ui.histogram.hide()
        self.contextZoomSplitter = QtWidgets.QSplitter(self)
        self.contextZoomSplitter.addWidget(self.contextImage)
        self.contextZoomSplitter.addWidget(self.zoomImage)

        self.mainSplitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.options = QtWidgets.QPushButton("Options", self)
        self.options.clicked.connect(self.showMenu)

        self.menuButton = QMenu(self)
        self.menuButton.addAction("Poly ROI", self.addPolylineROI)

        self.menuButton.addAction("Save ROI", self.saveROI)
        self.menuButton.addAction("Load ROI", self.loadROI)

        self.mainSplitter.addWidget(self.options)
        self.mainSplitter.addWidget(self.mainImage)
        self.mainSplitter.addWidget(self.contextZoomSplitter)
        layout.addWidget(self.mainSplitter)

        self.setLayout(layout)

    @override
    def dragEnterEvent(self, event, **kwargs):
        # TODO: Allow other file extensions
        if event.mimeData().urls()[0].toLocalFile().endswith('.hdr'):
            event.acceptProposedAction()

    @override
    def dropEvent(self, event, **kwargs):
        self.loadNewImage(str(Path(event.mimeData().urls()[0].toLocalFile())))

    def loadNewImage(self, fileName):
        print('Loading image...')
        self.sdv = speclab.SpectralImage.new_image(fileName)
        self.mainImage.currentBands = self.sdv.meta["default bands"]

        print("sdv data shape: " + str(self.sdv.data.shape))

        img = self.sdv.data[:, :, list(self.currentBands.values())].data

        if self.plot is None:
            self.initializePlot()
        else:
            self.plot.plotItem.clear()
            self.plot.plotItem.plot(self.sdv.calculate_mean())

        levels = (0, 1)
        axes = {'x': 1, 'y': 0, 'c': 2, 't': None}
        self.mainImage.setImage(img, autoLevels=False, levels=levels, axes=axes, autoHistogramRange=False)
        self.contextImage.setImage(img, autoLevels=False, levels=levels, axes=axes, autoHistogramRange=False)
        self.zoomImage.setImage(img, autoLevels=False, levels=levels, axes=axes, autoHistogramRange=False)

        self.updateImage()
        self.show()

    def initializePlot(self):

        self.currentBands = self.sdv.meta["default bands"]

        wavelength = self.sdv.meta["wavelength"]
        if wavelength is None:
            wavelength = np.arange(self.sdv.meta["bands"])
        minWavelength = min(wavelength)
        maxWavelength = max(wavelength)

        # construct plot
        self.plot = pg.plot(x=wavelength, y=self.sdv.calculate_mean(),
                            title="Frequency Plot", labels={'left': 'Average Strength', 'bottom': 'Frequency'})
        self.plot.setMouseEnabled(x=False, y=False)

        # construct red band selector
        self.redBandSelect = InfiniteLine(pos=wavelength[self.sdv.meta["default bands"]['r']], movable=True)
        self.redBandSelect.setPen(color='r', width=2)
        self.redBandSelect.setZValue(1)
        self.redBandSelect.setBounds((minWavelength, maxWavelength))
        self.redBandSelect.sigPositionChanged.connect(self.redBandChanged)

        # construct green band selector
        self.greenBandSelect = InfiniteLine(pos=wavelength[self.sdv.meta["default bands"]['g']], movable=True)
        self.greenBandSelect.setPen(color='g', width=2)
        self.greenBandSelect.setZValue(1)
        self.greenBandSelect.setBounds((minWavelength, maxWavelength))
        self.greenBandSelect.sigPositionChanged.connect(self.greenBandChanged)

        # construct blue band selector
        self.blueBandSelect = InfiniteLine(pos=wavelength[self.sdv.meta["default bands"]['b']], movable=True)
        self.blueBandSelect.setPen(color='blue', width=2)
        self.blueBandSelect.setZValue(1)
        self.blueBandSelect.setBounds((minWavelength, maxWavelength))
        self.blueBandSelect.sigPositionChanged.connect(self.blueBandChanged)

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
        img = self.sdv.data[:, :, list(self.currentBands.values())].data
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

        if self.sdv.meta["wavelength"] is None:
            return int(val), val

        inds = np.where(self.sdv.meta["wavelength"] <= val)

        if len(inds) < 1:
            return 0, val

        ind = inds[-1][-1]
        print("INDEX: ", ind)
        return ind, val

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
        self.currentROI.setPen(mkPen(cosmetic=False, width=2, color=Colors[color_keys[len(self.currentROIs)]]))
        self.currentROIs.append(self.currentROI)

        for ROI in self.currentROIs:
            self.mainImage.addItem(ROI)
