import sys
import numpy as np
import rasterio
from PyQt6.QtCore import QPointF
from rasterio.transform import Affine
from pathlib import Path

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QTransform


import pyqtgraph as pg

from varda.image_loading import ImageLoadingService
from varda.image_rendering.stretch_algorithms import (
    LinearPercentileStretch,
)


def affineToQTransform(affine: Affine) -> QTransform:
    return QTransform(
        affine.a,
        affine.d,
        affine.b,
        affine.e,
        affine.c,
        affine.f,
    )


class SpatialViewBox(pg.ViewBox):
    def __init__(self, affine: Affine, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.affine = affine
        self.qtransform = affineToQTransform(affine)

    def mapSceneToWorld(self, point: QPointF):
        """Scene → World coords (CRS units)."""
        pxy = self.mapFromScene(point)
        col, row = pxy.x(), pxy.y()
        return rasterio.transform.xy(self.affine, row, col, offset="center")

    def mapWorldToScene(self, xyPoint: QPointF):
        """World (CRS units) → Scene coords."""
        row, col = rasterio.transform.rowcol(self.affine, xyPoint.x(), xyPoint.y())
        return self.mapToScene(pg.Point(col, row))

    def addItem(self, item, applyTransform=False, *args, **kwargs):
        """
        If an item is in pixel coords and needs to be transformed, set applyTransform=True.
        If it's already in geo coords, applyTransform=False.
        """
        if applyTransform:
            item.setTransform(self.qtransform)
        super().addItem(item, *args, **kwargs)


def main():
    app = QApplication(sys.argv)

    imageLoadingService = ImageLoadingService()
    raster, metadata = imageLoadingService.load_image_sync(
        str(
            Path("../../testImages/Data/CRISM/frt00012dfa_07_if164j_mtr3.img").resolve()
        )
    )
    print("Image done loading.")
    rgbData = raster[:, :, [1, 2, 3]]
    stretch = LinearPercentileStretch()
    stretch.lowPercent.set(1)
    stretch.highPercent.set(99)

    rgbData = stretch.apply(rgbData)
    rgbData = rgbData.filled(1)
    affine = metadata.transform

    pg.setConfigOptions(imageAxisOrder="row-major")
    win = pg.GraphicsLayoutWidget(show=True, title="SpatialViewBox + ROI Demo")

    vb = SpatialViewBox(affine, lockAspect=True)
    win.addItem(vb)

    img = pg.ImageItem(rgbData, levels=(0, 1.0))
    # transformTest = QTransform()
    # transformTest.translate(100, 100)
    # transformTest.shear(0.1, 0.1)
    vb.addItem(img, applyTransform=True)

    testROI = pg.RectROI(
        [-2714899.998086924, -1678862.137770783],
        [1000, 1000],
        pen=pg.mkPen("r", width=2),
    )
    vb.addItem(testROI)

    # Mouse move callback
    def mouseMoved(evt):
        # evt is in scene coords

        viewCoords = vb.mapSceneToView(evt[0])
        print(f"ViewBox coords: {viewCoords.x()}, {viewCoords.y()}")
        px, py = rasterio.transform.rowcol(affine, viewCoords.x(), viewCoords.y())
        print(f"Pixel coords: {px}, {py}")

    proxy = pg.SignalProxy(win.scene().sigMouseMoved, rateLimit=60, slot=mouseMoved)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
