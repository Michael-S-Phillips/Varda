# base_tool.py
from PyQt6.QtCore import QObject, QPointF, pyqtSignal, QEvent
from PyQt6.QtGui import QMouseEvent, QKeyEvent
from PyQt6.QtWidgets import QGraphicsSceneMouseEvent


class Tool(QObject):
    """
    Abstract base class for all tools.
    """

    sigActivated = pyqtSignal()
    sigDeactivated = pyqtSignal()

    def __init__(self, viewport, parent=None):
        super().__init__(parent)
        self.viewport = viewport

    def activate(self):
        self.viewport.installEventFilter(self)
        self.sigActivated.emit()

    def deactivate(self):
        self.viewport.removeEventFilter(self)
        self.sigDeactivated.emit()

    def eventFilter(self, obj, event):
        t = event.type()

        # graphics‐scene mouse events
        if t == QEvent.Type.GraphicsSceneMousePress:
            return self.mousePressEvent(event)
        if t == QEvent.Type.GraphicsSceneMouseMove:
            return self.mouseMoveEvent(event)
        if t == QEvent.Type.GraphicsSceneMouseRelease:
            return self.mouseReleaseEvent(event)

        # keyboard
        if t == QEvent.Type.KeyPress:
            return self.keyPressEvent(event)

        return False

    # tools override the ones they need:
    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> bool:
        return False

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> bool:
        return False

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> bool:
        return False

    def keyPressEvent(self, event: QKeyEvent) -> bool:
        return False
