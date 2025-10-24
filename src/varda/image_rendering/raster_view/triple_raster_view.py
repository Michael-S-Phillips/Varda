from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QSplitter

from varda.image_rendering.image_renderer import ImageRenderer
from varda.rois.varda_roi import VardaROIItem
from varda.common.entities import Band, Stretch
from varda.image_rendering.raster_view.viewport import ImageViewport
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
        self.imageRenderer.sigShouldRefresh.connect(self.viewport1.refresh)
        self.viewport2 = ImageViewport(self.imageRenderer)
        self.viewport3 = ImageViewport(self.imageRenderer)

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
        startPoint = self.viewport1.imageItem.localToImage((50, 50))
        roiTempIndex = -1  # temp -- ROIs probably dont need an index field at all
        self.roi1 = VardaROIItem.rectROI(
            startPoint,
            (100, 100),
            roiTempIndex,
            QColor(255, 0, 0, 0),
            aspectLocked=True,
        )
        startPoint = self.viewport2.imageItem.localToImage((25, 25))
        self.roi2 = VardaROIItem.rectROI(
            startPoint,
            (50, 50),
            roiTempIndex,  # temp -- ROIs probably dont need an index field at all
            QColor(255, 0, 0, 0),
            aspectLocked=True,
        )

        self.mainController = RegionController(self.viewport1, self.viewport2, self.roi1)
        self.zoomController = RegionController(
            self.viewport2, self.viewport3, self.roi2, self.mainController
        )

    def setStretch(self, stretch: Stretch):
        self.viewport1.setStretch(stretch, update=False)
        self.viewport2.setStretch(stretch, update=False)
        self.viewport3.setStretch(stretch, update=False)
        self.viewport1.refresh()  # will cascade to others because of the ROIRegionControllers

    def setBand(self, band: Band):
        self.viewport1.setBand(band, update=False)
        self.viewport2.setBand(band, update=False)
        self.viewport3.setBand(band, update=False)
        self.viewport1.refresh()  # will cascade to others because of the ROIRegionControllers

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
