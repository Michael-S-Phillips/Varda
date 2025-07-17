from typing import Optional, Type

from PyQt6.QtCore import QObject, pyqtSignal, QEvent
from PyQt6.QtWidgets import QToolBar
from PyQt6.QtGui import QActionGroup

from varda.features.components.protocols import Viewport, ViewportTool
from varda.features.components.viewport_tools.tool_registry import ToolRegistry


class ToolManager(QObject):
    """
    Manager for viewport tools.

    Manages tools for a single viewport, ensuring that only one tool is active at a time.
    """

    sigToolActivated = pyqtSignal(object)  # Emits the activated tool
    sigToolDeactivated = pyqtSignal(object)  # Emits the deactivated tool

    def __init__(self, viewport: Viewport, parent=None):
        super().__init__(parent)
        self.viewport = viewport
        self.viewport.installEventFilter(self)
        self.activeTool: Optional[ViewportTool] = None
        self.toolRegistry = ToolRegistry()
        self.toolBar = self._createToolbar()

    def getToolbar(self):
        """Get the toolbar for this viewport."""
        return self.toolBar

    def activateTool(self, toolClass: Type[ViewportTool]):
        """Set the active tool and install only mouse event filters."""
        if self.activeTool:
            self.deactivateCurrentTool()

        self.activeTool = toolClass(self.viewport, parent=self)
        self.activeTool.activate()

    def deactivateCurrentTool(self):
        """Deactivate the currently active tool."""
        if self.activeTool is None:
            return
        # Deactivate the tool
        self.activeTool.deactivate()
        self.sigToolDeactivated.emit(self.activeTool)
        self.activeTool = None

    def eventFilter(self, obj, event):
        """
        This is specifically for forwarding KeyPress events to the active tool.
        Otherwise, the KeyPress events get consumed before reaching the imageItem.
        """
        if event.type() == QEvent.Type.KeyPress and self.activeTool is not None:
            return self.activeTool.eventFilter(obj, event)
        return False

    def _createToolbar(self) -> QToolBar:
        """Create a toolbar with actions for all available tools."""
        toolbar = QToolBar("Tools")

        # Create action group for mutual exclusion
        actionGroup = QActionGroup(toolbar)
        actionGroup.setExclusive(True)

        # Get all registered tools from the registry

        # Add tools by category
        currentCategory = None

        # Sort categories to ensure consistent order
        categories = sorted(self.toolRegistry.getCategories())

        for category in categories:
            # Add separator between categories
            if currentCategory is not None:
                toolbar.addSeparator()

            currentCategory = category

            # Get tools in this category
            tools = self.toolRegistry.getToolsByCategory(category)

            # Sort tools by name for consistent order
            tools.sort(key=lambda t: t.toolName)

            # Add each tool's action to the toolbar
            for toolClass in tools:
                action = toolClass.createAction(toolbar)
                action.triggered.connect(
                    lambda checked, tc=toolClass: self._onToolTriggered(tc)
                )
                actionGroup.addAction(action)
                toolbar.addAction(action)

        return toolbar

    def _onToolTriggered(self, toolClass: Type[ViewportTool]):
        """
        Handle tool activation.

        Args:
            toolClass: The tool class to activate
        """
        self.activateTool(toolClass)
