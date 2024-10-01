"""
spectralimageworkspace.py
A QtWidget which acts as a workspace for a single spectral image.
Including a main image display, context image, and zoom image.

NOTE: This is where we'll handle getting the views to interact with each other.
"""
from pathlib import Path
from typing import override
from PyQt6 import QtCore, QtGui, QtWidgets
from speclabgui.customwidgets.spectralimagedisplays import SpectralMainImageDisplay, SpectralZoomImage, SpectralContextImage
import speclabimageprocessing as speclab

class SpectralImageWorkspace(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(SpectralImageWorkspace, self).__init__(parent)
        self.setAcceptDrops(True)

        self.sdv = None

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
        # TODO: Verify that file is an .hdr (or other valid format) before accepting event
        event.acceptProposedAction()

    @override
    def dropEvent(self, event, **kwargs):
        self.loadNewImage(str(Path(event.mimeData().urls()[0].toLocalFile())))

    def loadNewImage(self, fileName):
        print('Loading image...')
        sdv = speclab.SpectralImage.new_image(fileName)
        self.mainImage.setImage(sdv.image)
        self.contextImage.setImage(sdv.image)
        self.zoomImage.setImage(sdv.image)
        self.show()
