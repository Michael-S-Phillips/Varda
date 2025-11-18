from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QSplitter

from varda.image_rendering.image_renderer import ImageRenderer
from varda.rois.varda_roi import VardaROIItem
from varda.image_rendering.raster_view.image_viewport import ImageViewport
from varda.image_rendering.raster_view.region_controller import (
    RegionController,
)


class TripleRasterView(QWidget):
    def __init__(self, imageRenderer: ImageRenderer, parent=None):
        super().__init__(parent)
        self.imageRenderer = imageRenderer
        self._initUI()
        self._initROIControllers()

    def _initUI(self):
        self.viewport1 = ImageViewport(self.imageRenderer)
        # only need to connect one first viewport, because others are linked via region controllers
        self.viewport2 = ImageViewport(self.imageRenderer)
        self.viewport2.disableSelfUpdating()
        self.viewport3 = ImageViewport(self.imageRenderer)
        self.viewport3.disableSelfUpdating()

        # top-level layout
        verticalSplitter = QSplitter(Qt.Orientation.Vertical)
        verticalSplitter.addWidget(self.viewport1)
        verticalSplitter.addWidget(self.viewport3)

        horizontalSplitter = QSplitter(Qt.Orientation.Horizontal)
        horizontalSplitter.addWidget(self.viewport2)
        horizontalSplitter.addWidget(verticalSplitter)

        layout = QVBoxLayout(self)
        layout.addWidget(horizontalSplitter)
        self.setLayout(layout)

    def _initROIControllers(self):
        """Initialize ROI controllers for the viewports"""
        imageShape = self.viewport1.imageItem.image.shape
        height, width = imageShape[0], imageShape[1]

        startPoint = width // 3, height // 3
        size = width // 3, height // 3
        roiTempIndex = -1  # temp -- ROIs probably dont need an index field at all
        self.roi1 = VardaROIItem.rectROI(
            startPoint,
            size,
            roiTempIndex,
            QColor(255, 0, 0, 0),
            aspectLocked=True,
        )

        startPoint = startPoint[0] // 3, startPoint[1] // 3
        size = size[0] // 3, size[1] // 3
        self.roi2 = VardaROIItem.rectROI(
            startPoint,
            size,
            roiTempIndex,  # temp -- ROIs probably dont need an index field at all
            QColor(255, 0, 0, 0),
            aspectLocked=True,
        )

        self.mainController = RegionController(
            self.viewport1, self.viewport2, self.roi1
        )
        self.zoomController = RegionController(
            self.viewport2, self.viewport3, self.roi2, self.mainController
        )

    def addToolbarToViewport(self, viewport, toolbar):
        """Add a toolbar to a specific viewport."""
        if viewport is self.viewport1:
            self.viewport1.addToolBar(toolbar)
        elif viewport is self.viewport2:
            self.viewport2.addToolBar(toolbar)
        elif viewport is self.viewport3:
            self.viewport3.addToolBar(toolbar)
        else:
            raise ValueError("Invalid viewport specified.")
