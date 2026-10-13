"""ROI outlines are clipped to the displayed image, so a zoom panel never shows
the parts of ROIs that lie outside its region."""

import pyqtgraph as pg
from PyQt6.QtCore import QPointF, QRectF
from PyQt6.QtGui import QColor, QImage, QPainter

from varda.image_rendering.raster_view.overlay_handles import PyqtgraphROIOverlay


def test_an_roi_paints_only_inside_its_clip_rect(qtbot):
    viewBox = pg.ViewBox()
    square = [QPointF(0, 0), QPointF(40, 0), QPointF(40, 40), QPointF(0, 40)]
    overlay = PyqtgraphROIOverlay(
        viewBox, square, QColor(255, 0, 0, 255), clipTo=lambda: QRectF(0, 0, 20, 20)
    )
    image = QImage(50, 50, QImage.Format.Format_ARGB32)
    image.fill(QColor(0, 0, 0, 0))
    painter = QPainter(image)
    overlay.paint(painter, None)
    painter.end()
    assert image.pixelColor(10, 10).alpha() > 0
    assert image.pixelColor(30, 30).alpha() == 0
