"""
Protocol for viewport tools that can be used to interact with viewports.
"""

from PyQt6.QtCore import QObject, pyqtSignal, QEvent
from PyQt6.QtGui import QKeyEvent, QIcon, QAction
from PyQt6.QtWidgets import QGraphicsSceneMouseEvent

from varda.app.protocols.viewport_protocol import Viewport


class ViewportTool(QObject):
    """
    Abstract base class for all viewport tools.

    Tools can define their own QActions for use in toolbars by implementing
    the createAction class method.
    """

    sigActivated = pyqtSignal()
    sigDeactivated = pyqtSignal()

    # Class attributes that subclasses should override
    toolName = "Generic Tool"
    toolDescription = "Base tool class"
    toolIcon = None  # Path to icon or QIcon
    toolCategory = "General"

    def __init__(self, viewport: Viewport, parent=None):
        super().__init__(parent)
        self.viewport = viewport
        self._textItem = None
        self._textVisible = False

    @classmethod
    def createAction(cls, parent=None) -> QAction:
        """
        Create a QAction for this tool that can be added to a toolbar.

        Returns:
            QAction: An action that can be used to activate this tool
        """
        action = QAction(cls.toolName, parent)
        action.setToolTip(cls.toolDescription)
        action.setCheckable(True)

        # Set icon if available
        if cls.toolIcon:
            if isinstance(cls.toolIcon, str):
                action.setIcon(QIcon(cls.toolIcon))
            else:
                action.setIcon(cls.toolIcon)

        # Store the tool class in the action's data
        action.setData(cls)

        return action

    def activate(self):
        self.viewport.installTool(self)
        self.sigActivated.emit()

    def deactivate(self):
        self.viewport.removeTool(self)
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

    # Tools override the ones they need:
    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> bool:
        return False

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> bool:
        return False

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> bool:
        return False

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent) -> bool:
        return False

    def keyPressEvent(self, event: QKeyEvent) -> bool:
        return False
