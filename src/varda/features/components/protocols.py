import logging
from typing import Protocol

import pyqtgraph as pg
from PyQt6.QtCore import QObject, QPointF, pyqtSignal, QEvent, QTimer
from PyQt6.QtGui import QKeyEvent, QIcon, QAction, QCursor
from PyQt6.QtWidgets import QGraphicsSceneMouseEvent

from varda.common.entities import Image
from varda.features.components.raster_view import VardaImageItem

logger = logging.getLogger(__name__)


class Viewport(Protocol):
    """
    Protocol for a viewport, which is a widget that displays image data.
    The purpose of this is to generalize an interface that can be used by controllers/viewport_tools/workspaces.
    """

    sigImageChanged: pyqtSignal

    def enableSelfUpdating(self):
        """Enable self-updating of the image item."""

    def disableSelfUpdating(self):
        """Disable self-updating of the image item."""

    def setBand(self, band):
        """Set the band for the image item."""

    def setStretch(self, stretch):
        """Set the stretch for the image item."""

    def refresh(self):
        """Refresh the image display with current settings."""

    def addItem(self, item):
        """Add a graphics item to the viewport"""

    def removeItem(self, item):
        """Remove a graphics item from the viewport"""

    def installTool(self, tool):
        """Install a tool on the viewport."""

    def removeTool(self, tool):
        """Remove a tool from the viewport."""

    def addToolBar(self, toolbar):
        """Add a toolbar to the viewport."""

    @property
    def imageItem(self) -> VardaImageItem:
        """Get the ImageRegionItem for this viewport."""
        ...

    @property
    def imageEntity(self) -> Image:
        """Get the Image entity for this viewport."""
        ...

    @property
    def viewBox(self) -> pg.ViewBox:
        """Get the ViewBox for this viewport."""
        ...

    @property
    def graphicsScene(self):
        """Get the GraphicsScene for this viewport."""
        ...


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

    # TODO: This probably should be its own separate service or something.
    #  It also could be improved. eg. there is no easy way to center text in the viewbox.
    def showText(
        self,
        text,
        pos=None,
        color="white",
        font_size=12,
        background_color="black",
        background_alpha=150,
        anchor=(0, 0),
        timeout=None,
    ):
        """
        Display text on the viewport using pyqtgraph's TextItem.

        Args:
            text (str): The text to display
            pos (QPointF, tuple, or None): Position in scene coordinates.
                If None, uses current mouse position
            color (str): Text color (CSS color name or hex)
            font_size (int): Font size in points
            background_color (str): Background color (CSS color name or hex)
            background_alpha (int): Background alpha (0-255)
            anchor (tuple): Text anchor point (0,0) = top-left, (1,1) = bottom-right
            timeout (int, None): Auto-hide timeout in milliseconds. None = no timeout
        """

        # Remove existing text item if it exists
        if self._textItem is not None:
            self.hideText()

        # Create new text item
        self._textItem = pg.TextItem(text=text, color=color, anchor=anchor)

        # Set font size
        font = self._textItem.textItem.font()
        font.setPointSize(font_size)
        self._textItem.textItem.setFont(font)

        # Set background
        if background_color:
            self._textItem.fill = pg.mkBrush(
                color=background_color, alpha=background_alpha
            )
            self._textItem.border = pg.mkPen(color=background_color, width=1)

        # Determine position
        if pos is None:
            globalCursorPos = QCursor.pos()
            localCursorPos = self.viewport.mapFromGlobal(globalCursorPos).toPointF()
            pos = self.viewport.viewBox.mapToScene(localCursorPos)
        elif isinstance(pos, (tuple, list)):
            pos = QPointF(pos[0], pos[1])

        # Set position and add to scene
        self._textItem.setPos(pos)
        self.viewport.addItem(self._textItem)
        self._textVisible = True

        # Set up timeout if specified
        if timeout is not None:

            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(self.hideText)
            timer.start(timeout)

    def hideText(self):
        """Hide the currently displayed text."""
        if self._textItem is not None and self._textVisible:
            try:
                self.viewport.removeItem(self._textItem)
            except:
                logger.warning(
                    "Failed to remove text item from viewport. It may have already been removed."
                )
            self._textItem = None
            self._textVisible = False

    def updateText(self, text):
        """Update the text content without changing position or style."""
        if self._textItem is not None and self._textVisible:
            self._textItem.setText(text)

    def moveText(self, pos):
        """Move the text to a new position."""
        if self._textItem is not None and self._textVisible:
            if isinstance(pos, (tuple, list)):
                pos = QPointF(pos[0], pos[1])
            self._textItem.setPos(pos)

    def isTextVisible(self):
        """Check if text is currently visible."""
        return self._textVisible

    def showTooltip(self, text, pos=None, timeout=3000):
        """
        Convenience method to show a tooltip-style text display.

        Args:
            text (str): Tooltip text
            pos (QPointF, tuple, or None): Position in scene coordinates
            timeout (int): Auto-hide timeout in milliseconds
        """
        self.showText(
            text=text,
            pos=pos,
            color="black",
            font_size=10,
            background_color="lightyellow",
            background_alpha=200,
            anchor=(0, 1),  # Bottom-left anchor for tooltip style
            timeout=timeout,
        )

    def showStatusText(self, text, pos=None):
        """
        Convenience method to show persistent status text.

        Args:
            text (str): Status text
            pos (QPointF, tuple, or None): Position in scene coordinates
        """
        self.showText(
            text=text,
            pos=pos,
            color="lime",
            font_size=11,
            background_color="darkgreen",
            background_alpha=180,
            anchor=(0, 0),
            timeout=None,  # No timeout for status text
        )

    def showErrorText(self, text, pos=None, timeout=5000):
        """
        Convenience method to show error text.

        Args:
            text (str): Error message
            pos (QPointF, tuple, or None): Position in scene coordinates
            timeout (int): Auto-hide timeout in milliseconds
        """
        self.showText(
            text=text,
            pos=pos,
            color="white",
            font_size=12,
            background_color="red",
            background_alpha=200,
            anchor=(0.5, 0.5),  # Center anchor for error messages
            timeout=timeout,
        )
