from PyQt6.QtCore import pyqtSignal
import pyqtgraph as pg
import numpy as np

# Class to handle freehand drawn ROI's with pyqt graphicsobjects
class ROISelector(pg.GraphicsObject):

    sigDrawingComplete = pyqtSignal()
    def __init__(self, color=None):
        pg.GraphicsObject.__init__(self)
        self.pts = None
        self.path = None
        self.color = color if color else (0, 0, 255, 100)
        self.imageIndex = None

    # Method to handle user drawing
    def draw(self):
        self.pts = None
        self.path = None
        self.scene().installEventFilter(self)
        self.prepareGeometryChange()

    def setImageIndex(self, indx):
        self.imageIndex = indx

    # Method to handle user initiated events
    def eventFilter(self, obj, ev):
        if ev.type() == ev.Type.GraphicsSceneMousePress:
            self.addPathPoint(self.mapFromScene(ev.scenePos()))
            ev.accept()
            return True  # prevent scene from receiving this event
        elif ev.type() == ev.Type.GraphicsSceneMouseMove:
            if self.pts is not None:
                self.addPathPoint(self.mapFromScene(ev.scenePos()))
            return True
        elif ev.type() == ev.Type.GraphicsSceneMouseRelease:
            ev.accept()
            self.path.closeSubpath()
            self.scene().removeEventFilter(self)
            self.sigDrawingComplete.emit()  
            return True
        else:
            return False

    # Method to add a point to the path drawn by the user
    def addPathPoint(self, pt):
        if self.pts is None:
            self.pts = [[pt.x()], [pt.y()]]
        else:
            self.pts[0].append(pt.x())
            self.pts[1].append(pt.y())
        self.path = pg.arrayToQPath(np.array(self.pts[0]),
                                    np.array(self.pts[1]))
        self.prepareGeometryChange()

    # Method to return a bounding rectangle as an ROI if needed.
    def boundingRect(self):
        if self.path is None:
            return pg.QtCore.QRectF()
        return self.path.boundingRect()

    # Handles graphic parameters for user drawing
    def paint(self, p, *args):
        if self.path is None:
            return
        p.setRenderHints(p.renderHints() |
                            p.RenderHint.Antialiasing)
        p.setPen(pg.mkPen(self.color[:3]))  # Outline color
        p.drawPath(self.path)
        p.fillPath(self.path, pg.mkBrush(*self.color))  # Fill color

    # Returns a list of two lists,
    # list[0] are all x values, list[1] are all y values
    def getLinePts(self):
        return self.pts

