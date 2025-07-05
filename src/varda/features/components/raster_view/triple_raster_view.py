from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QSplitter
import pyqtgraph as pg

from varda.app.services.roi_utils import VardaROIItem
from varda.core.data import ProjectContext
from varda.core.entities import Image, Band, Stretch
from varda.features.components.raster_view.raster_viewport import ImageViewport
from varda.features.components.raster_view.roi_region_controller import (
    ROIRegionController,
)


class TripleRasterView(QWidget):
    def __init__(self, imageIndex: int, proj: ProjectContext, parent=None):
        super().__init__(parent)
        self.imageIndex = imageIndex
        self.image = proj.getImage(imageIndex)
        self._initUI()
        self._initROIControllers()

    def _initUI(self):
        self.viewport1 = ImageViewport(self.image)
        self.viewport2 = ImageViewport(self.image)
        self.viewport3 = ImageViewport(self.image)

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

        # # Create test ROI with no controllers to verify basic visibility
        # test_roi = VardaROI.rectROI(
        #     (200, 200),
        #     (150, 150),
        #     self.imageIndex,
        #     (0, 255, 0, 100),  # Bright green
        # )
        #
        # # Add directly to viewport with no controllers
        # self.viewport1.addItem(test_roi)

        # Create ROIs
        self.roi1 = VardaROIItem.rectROI(
            (50, 50),
            (100, 100),
            self.imageIndex,
            QColor(255, 0, 0, 0),
            aspectLocked=True,
        )
        self.roi2 = VardaROIItem.rectROI(
            (25, 25), (50, 50), self.imageIndex, QColor(255, 0, 0, 0), aspectLocked=True
        )

        self.mainController = ROIRegionController(
            self.viewport1, self.viewport2, self.roi1
        )
        self.zoomController = ROIRegionController(
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
