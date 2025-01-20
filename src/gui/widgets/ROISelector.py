import pyqtgraph as pg
import numpy as np

class ROISelector(pg.GraphicsObject):
    def __init__(self, raster):
        super().__init__()
        self.raster = raster  # The raster data of the image
        self.image_item = pg.ImageItem(self.raster)
        self.pts = None
        self.path = None

    def addToScene(self, scene):
        """Add the image and ROI drawing to a PyQtGraph scene."""
        scene.addItem(self.image_item)  # Add the image
        scene.addItem(self)  # Add this graphics object for ROI

    def draw(self):
        """Start drawing ROI."""
        print("here")
        print(self.scene())
        self.pts = None
        self.path = None
        self.scene().installEventFilter(self)
        self.prepareGeometryChange()

    def eventFilter(self, obj, ev):
        """Handle drawing events."""
        if ev.type() == ev.Type.GraphicsSceneMousePress:
            self.addPathPoint(self.mapFromScene(ev.scenePos()))
            ev.accept()
            return True
        elif ev.type() == ev.Type.GraphicsSceneMouseMove:
            if self.pts is not None:
                self.addPathPoint(self.mapFromScene(ev.scenePos()))
            return True
        elif ev.type() == ev.Type.GraphicsSceneMouseRelease:
            ev.accept()
            self.path.closeSubpath()
            self.scene().removeEventFilter(self)
            return True
        else:
            return False

    def addPathPoint(self, pt):
        """Add a point to the ROI path."""
        print("here2")
        print(self.pts)
        if self.pts is None:
            self.pts = [[pt.x()], [pt.y()]]
        else:
            self.pts[0].append(pt.x())
            self.pts[1].append(pt.y())
        self.path = pg.arrayToQPath(np.array(self.pts[0]),
                                    np.array(self.pts[1]))
        self.prepareGeometryChange()

    def boundingRect(self):
        """Bounding rectangle for the ROI."""
        if self.path is None:
            return pg.QtCore.QRectF()
        return self.path.boundingRect()

    def paint(self, p, *args):
        """Render the ROI path."""
        if self.path is None:
            return
        p.setRenderHints(p.renderHints() | p.RenderHint.Antialiasing)
        p.setPen(pg.mkPen('b'))
        p.drawPath(self.path)
        p.fillPath(self.path, pg.mkBrush(0, 0, 255, 100))

    def getLinePts(self):
        """Retrieve points of the drawn ROI."""
        return self.pts
