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

        self.red_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.red_slider.setValue(0)  # Set initial slice to 0
        self.red_slider.setTickInterval(1)
        self.red_slider.valueChanged.connect(self.updateSlice)

        self.green_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.green_slider.setValue(0)  # Set initial slice to 0
        self.green_slider.setTickInterval(1)
        self.green_slider.valueChanged.connect(self.updateSlice)

        self.blue_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.blue_slider.setValue(0)  # Set initial slice to 0
        self.blue_slider.setTickInterval(1)
        self.blue_slider.valueChanged.connect(self.updateSlice)

        layout.addWidget(self.red_slider)
        layout.addWidget(self.green_slider)
        layout.addWidget(self.blue_slider)

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
        self.sdv = speclab.SpectralImage.new_image(fileName)
        self.red_slider.setRange(0, self.sdv.data.shape[2] - 1)
        self.green_slider.setRange(0, self.sdv.data.shape[2] - 1)
        self.blue_slider.setRange(0, self.sdv.data.shape[2] - 1)

        self.mainImage.setImage(self.sdv.image, autoLevels=False)
        self.contextImage.setImage(self.sdv.image, autoLevels=False)
        self.zoomImage.setImage(self.sdv.image, autoLevels=False)
        self.show()

    def updateSlice(self, value):
        print("red band: " + str(self.red_slider.value()))
        print("green band: " + str(self.green_slider.value()))
        print("blue band: " + str(self.blue_slider.value()))

        slice_data = self.sdv.data[:, :, [self.red_slider.value(), self.green_slider.value(), self.blue_slider.value()]]  # Get the current slice

        # Update the image items
        self.mainImage.setImage(slice_data, autoLevels=False)
        #self.contextImage.setImage(slice_data)
        #self.zoomImage.setImage(slice_data)
