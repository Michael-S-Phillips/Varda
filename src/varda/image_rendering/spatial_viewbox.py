import pyqtgraph as pg
import rasterio as rio
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QTransform
from affine import Affine


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
    def __init__(self, affine: Affine, crs, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.affine = affine
        self.qtransform = affineToQTransform(affine)
        self.crs = crs

    def mapWorldToScene(self, px, py):
        row, col = rio.transform.rowcol(self.affine, px, py)
        return self.mapToScene(QPointF(col, row))

    def mapSceneToWorld(self, point: QPointF):
        pxy = self.mapFromScene(point)
        col, row = int(pxy.x()), int(pxy.y())
        return rio.transform.xy(self.affine, row, col)

    def addItem(self, item, applyTransform=False, *args, **kwargs):
        if applyTransform:
            item.setTransform(self.qtransform)
        super().addItem(item, *args, **kwargs)
