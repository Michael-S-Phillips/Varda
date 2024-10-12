"""
spectralimageworkspace.py
A QtWidget which acts as a workspace for a single spectral image.
Including a main image display, context image, and zoom image.

NOTE: This is where we'll handle getting the views to interact with each other.
"""
from pathlib import Path
from typing import override

import numpy as np
from PyQt6 import QtCore, QtGui, QtWidgets
from speclabgui.customwidgets.spectralimagedisplays import SpectralMainImageDisplay, SpectralZoomImage, SpectralContextImage
import speclabimageprocessing as speclab
import pyqtgraph as pg

class SpectralImageWorkspace(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(SpectralImageWorkspace, self).__init__(parent)
        self.setAcceptDrops(True)

        self.sdv = None
        self.plot = None

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

        print("sdv data shape: " + str(self.sdv.data.shape))
        self.mainImage.setImage(self.sdv.data, axes=self.sdv.axes, autoLevels=False, levels=(0, 1))
        self.contextImage.setImage(self.sdv.data, axes=self.sdv.axes, autoLevels=False, levels=(0, 1))
        self.zoomImage.setImage(self.sdv.data, axes=self.sdv.axes, autoLevels=False, levels=(0, 1))

        self.mainImage.currentBands = self.sdv.meta.default_bands
        if self.plot is None:
            self.plot = pg.plot(self.sdv.calculateMean(), title="Sine Wave Plot", labels={'left': 'Average Strength', 'bottom': 'Frequency'})
            self.mainSplitter.addWidget(self.plot)

        else:
            self.plot.plotItem.clear()
            self.plot.plotItem.plot(self.sdv.calculateMean())
        self.show()
