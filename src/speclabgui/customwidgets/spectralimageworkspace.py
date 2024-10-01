"""
spectralimageworkspace.py
A QtWidget which acts as a workspace for a single spectral image.
Including a main image display, context image, and zoom image.
"""
from pathlib import Path
from typing import override
import PyQt6.QtWidgets as QtWidgets
import PyQt6.QtCore as QtCore
import numpy as np

from speclabgui.customwidgets.spectralimagedisplay import SpectralImageDisplay, SpectralZoomImage, SpectralContextImage
import speclabimageprocessing as speclab

class SpectralImageWorkspace(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(SpectralImageWorkspace, self).__init__(parent)
        self.setAcceptDrops(True)

        self.sdv = None
        layout = QtWidgets.QVBoxLayout()

        self.mainSplitter = QtWidgets.QSplitter(self)

        self.mainImage = SpectralImageDisplay(parent)
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
        # if event.mimeData().hasFormat('image/hdr'):
        event.acceptProposedAction()

    @override
    def dropEvent(self, event, **kwargs):
        self.createPlt(str(Path(event.mimeData().urls()[0].toLocalFile())))

    def createPlt(self, fileName):


        print('Creating plt...')

        sdv = speclab.SpectralImage.new_image(fileName)
        # imv = pg.ImageView(self)
        imageArray = np.array(sdv.image)
        self.mainImage.setImage(imageArray)
        self.contextImage.setImage(imageArray)
        self.zoomImage.setImage(imageArray)
        self.show()
