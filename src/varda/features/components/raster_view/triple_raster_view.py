from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QSplitter
import pyqtgraph as pg

from varda.core.data import ProjectContext
from varda.core.entities import Image
from varda.features.components.raster_view.raster_viewport import ImageViewport
from varda.features.components.raster_view.roi_region_controller import (
    ROIRegionController,
)


class TripleRasterView(QWidget):
    def __init__(self, imageIndex: int, proj: ProjectContext, parent=None):
        super().__init__(parent)
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
        # Create ROIs
        self.roi1 = pg.RectROI(
            [0, 0],
            [100, 100],
            pen=(0, 9),
            maxBounds=self.viewport1.imageItem.boundingRect(),
            aspectLocked=True,
        )
        self.roi2 = pg.RectROI(
            [0, 0],
            [50, 50],
            pen=(0, 9),
            maxBounds=self.viewport1.imageItem.boundingRect(),
            aspectLocked=True,
        )

        self.mainController = ROIRegionController(
            self.viewport1, self.viewport2, self.roi1
        )
        self.zoomController = ROIRegionController(
            self.viewport2, self.viewport3, self.roi2
        )
