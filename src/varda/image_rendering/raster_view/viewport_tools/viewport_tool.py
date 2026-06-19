from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from PyQt6.QtGui import QAction, QIcon

from varda.image_rendering.raster_view.image_viewport import ImageViewport
from varda.image_rendering.raster_view.pointer_event import KeyEvent, PointerEvent

if TYPE_CHECKING:
    from varda.image_rendering.raster_view.viewport_protocol import TextOverlayHandle


logger = logging.getLogger(__name__)


class ViewportTool(QObject):
    """Abstract base class for all viewport tools.

    Tools receive backend-neutral `PointerEvent`s / `KeyEvent`s from the viewport
    (the viewport translates its scene events and pre-maps coordinates — see
    `ImageViewport.installTool`); they never touch Qt scene events or the pyqtgraph
    scene graph. Subclasses override `onPointerEvent` / `onKeyEvent` and return True
    when they consume an event.

    Tools can define their own QActions for use in toolbars by implementing
    the createAction class method.
    """

    sigActivated = pyqtSignal()
    sigDeactivated = pyqtSignal()
    # Emitted by a modal tool when its one-shot action completes, so a controller
    # can disarm the tool across every viewport. Persistent tools never emit it.
    sigCompleted = pyqtSignal()

    # Class attributes that subclasses should override
    toolName = "Generic Tool"
    toolDescription = "Base tool class"
    toolIcon = None  # Path to icon or QIcon
    toolCategory = "General"
    # Ambient tools are installed on every viewport permanently and never shown in
    # the toolbar (e.g. Pixel Select, which is gated on Ctrl+Click).
    isAmbient = False

    def __init__(self, viewport: ImageViewport, parent=None):
        super().__init__(parent)
        self.viewport = viewport
        self._textOverlay: TextOverlayHandle | None = None

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

    # --- Input handling: subclasses override the ones they need ---

    def onPointerEvent(self, event: PointerEvent) -> bool:
        """Handle a pointer (mouse) interaction. Return True if consumed."""
        return False

    def onKeyEvent(self, event: KeyEvent) -> bool:
        """Handle a key press. Return True if consumed."""
        return False

    # --- Transient on-canvas text ---

    def showText(self, text: str, timeout: int | None = None):
        """Show a transient text label at the top-left of the view.

        If `timeout` (milliseconds) is given, the label auto-hides after it.
        """
        self.hideText()
        self._textOverlay = self.viewport.addTextOverlay(text)
        if timeout is not None:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(self.hideText)
            timer.start(timeout)

    def hideText(self):
        """Hide the currently displayed text, if any."""
        if self._textOverlay is not None:
            self._textOverlay.remove()
            self._textOverlay = None

    def updateText(self, text: str):
        """Update the text content without changing position or style."""
        if self._textOverlay is not None:
            self._textOverlay.setText(text)
