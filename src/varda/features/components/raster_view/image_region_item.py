# third-party imports
import pyqtgraph as pg
from PyQt6.QtCore import QPointF


class ImageRegionItem(pg.ImageItem):
    """
    Custom ImageItem that supports only displaying a region of the image,
    with a convenience method to get the absolute image coordinates.
    """

    def __init__(self, image=None, **kwargs):
        super().__init__(image=image, **kwargs)
        self.region = None

    def setRegion(
        self, image: pg.ImageItem, region: pg.ROI, sourceImageItem: pg.ImageItem
    ):
        """Set the region of interest for zooming."""
        self.region = region
        rasterData = self.region.getArrayRegion(image, sourceImageItem)
        self.setImage(rasterData, autoLevels=False)

    def getAbsoluteCoords(self, point: QPointF):
        """Convert local zoomed coordinates to absolute image coordinates."""
        if self.region is None:
            return point
        # Calculate absolute coordinates based on the region
        abs_x = int(self.region.pos().x() + point.x())
        abs_y = int(self.region.pos().y() + point.y())
        return QPointF(abs_x, abs_y)

    def getLocalCoords(self, point: QPointF):
        """Convert absolute image coordinates to local zoomed coordinates."""
        if self.region is None:
            return point
        # Calculate local coordinates based on the region
        local_x = int(point.x() - self.region.pos().x())
        local_y = int(point.y() - self.region.pos().y())
        return QPointF(local_x, local_y)

    def getOffset(self):
        """Get the offset of the image item."""
        if self.region is None:
            return QPointF(0, 0)
        return self.region.pos()
