from typing import Optional, Type

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QToolBar
from PyQt6.QtGui import QActionGroup

from varda.features.components.generic_protocols import Viewport, ViewportTool
from varda.features.components.viewport_tools.tool_registry import ToolRegistry


class ToolManager(QObject):
    """
    Manager for viewport tools.

    Manages tools for a single viewport, ensuring that only one tool is active at a time.
    """

    sigToolActivated = pyqtSignal(object)  # Emits the activated tool
    sigToolDeactivated = pyqtSignal(object)  # Emits the deactivated tool
    sigROIDrawingComplete = pyqtSignal(object)  # Forwarded from ROI drawing tool
    sigROIDrawingCanceled = pyqtSignal(object)  # Forwarded from ROI drawing tool

    def __init__(self, viewport: Viewport, parent=None):
        super().__init__(parent)
        self.viewport = viewport
        self.activeTool: Optional[ViewportTool] = None
        self.toolRegistry = ToolRegistry()
        self.toolBar = self._createToolbar()

    def getToolbar(self):
        """Get the toolbar for this viewport."""
        return self.toolBar

    def activateTool(self, toolClass: Type[ViewportTool]):
        """
        Activate a tool on the viewport.

        Args:
            toolClass: The tool class to activate
        """
        # Deactivate current tool if any
        self.deactivateCurrentTool()

        # Create and activate the tool
        self.activeTool = toolClass(self.viewport)

        # Activate the tool
        self.activeTool.activate()

        # Emit signal
        self.sigToolActivated.emit(self.activeTool)

    def deactivateCurrentTool(self):
        """Deactivate the currently active tool."""
        if self.activeTool is not None:
            # Deactivate the tool
            self.activeTool.deactivate()
            self.sigToolDeactivated.emit(self.activeTool)
            self.activeTool = None

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
