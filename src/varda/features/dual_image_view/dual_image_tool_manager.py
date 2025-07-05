"""
Dual Image Tool Manager

Manages tool lifecycle, event routing, and UI coordination for dual image view viewport_tools.
Follows the established manager pattern used throughout Varda.
"""

import logging
from typing import Dict, List, Optional, Type, Any
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QScrollArea, QSplitter

from varda.core.data import ProjectContext
from .dual_image_tool_base import DualImageToolBase

logger = logging.getLogger(__name__)


class DualImageToolManager(QObject):
    """
    Manager for dual image view viewport_tools.

    Coordinates tool activation, event routing, and UI management.
    Integrates with the dual image view controller architecture.
    """

    # Signals
    tool_activated = pyqtSignal(str)  # tool_name
    tool_deactivated = pyqtSignal(str)  # tool_name
    click_handled = pyqtSignal(
        str, int, int, int, str
    )  # tool_name, image_index, x, y, view_type

    def __init__(self, project_context: ProjectContext, parent=None):
        super().__init__(parent)
        self.proj = project_context

        # Tool registry and state
        self._registered_tools: Dict[str, Type[DualImageToolBase]] = {}
        self._active_tools: Dict[str, DualImageToolBase] = {}
        self._tool_instances: Dict[str, DualImageToolBase] = {}

        # Current image pair
        self._primary_index: Optional[int] = None
        self._secondary_index: Optional[int] = None

        # UI components
        self._tool_panel_widget: Optional[QWidget] = None
        self._tool_scroll_area: Optional[QScrollArea] = None

        # Click handling state
        self._click_routing_enabled = True

        logger.debug("DualImageToolManager initialized")

    def register_tool(self, tool_class: Type[DualImageToolBase], tool_name: str = None):
        """
        Register a new tool class.

        Args:
            tool_class: Class that inherits from DualImageToolBase
            tool_name: Optional name override (uses class default if None)
        """
        if tool_name is None:
            # Create instance temporarily to get tool name
            temp_instance = tool_class("temp", self.proj)
            tool_name = temp_instance.tool_name
            del temp_instance

        self._registered_tools[tool_name] = tool_class
        logger.debug(f"Registered tool: {tool_name}")

    def set_default_tool(self, tool_name: str):
        """Set and activate a default tool"""
        if tool_name in self._registered_tools:
            self.activate_tool(tool_name)
            logger.info(f"Set default tool: {tool_name}")
        else:
            logger.error(f"Cannot set default tool '{tool_name}' - not registered")

    def switch_active_tool(self, new_tool_name: str) -> bool:
        """
        Switch from current active tool to a new tool.
        Ensures only one tool is active at a time in the canvas.

        Args:
            new_tool_name: Name of tool to switch to

        Returns:
            bool: True if switch was successful
        """
        # Get currently active viewport_tools
        current_active = list(self._active_tools.keys())

        # If the new tool is already active, nothing to do
        if new_tool_name in current_active and len(current_active) == 1:
            logger.debug(f"Tool '{new_tool_name}' is already the active tool")
            return True

        # Deactivate all current viewport_tools
        for tool_name in current_active:
            if not self.deactivate_tool(tool_name):
                logger.warning(f"Failed to deactivate tool '{tool_name}' during switch")

        # Activate the new tool
        if self.activate_tool(new_tool_name):
            logger.info(f"Successfully switched to tool: {new_tool_name}")
            return True
        else:
            logger.error(f"Failed to switch to tool: {new_tool_name}")
            return False

    def get_active_tool(self) -> Optional[str]:
        """Get the currently active tool (should be only one in canvas mode)"""
        active_tools = list(self._active_tools.keys())
        if len(active_tools) == 1:
            return active_tools[0]
        elif len(active_tools) == 0:
            return None
        else:
            logger.warning(f"Multiple viewport_tools active: {active_tools}")
            return active_tools[0]  # Return first one

    def ensure_tool_active(self, preferred_tool: str = "spectral_plot") -> str:
        """
        Ensure at least one tool is active, activating preferred tool if none active.

        Args:
            preferred_tool: Tool to activate if none are currently active

        Returns:
            str: Name of the active tool
        """
        current_active = self.get_active_tool()
        if current_active:
            return current_active

        # No tool active, activate preferred
        if self.activate_tool(preferred_tool):
            logger.info(f"Activated default tool: {preferred_tool}")
            return preferred_tool
        else:
            logger.error(f"Failed to activate default tool: {preferred_tool}")
            return None

    def activate_tool(self, tool_name: str) -> bool:
        """
        Activate a specific tool.

        Args:
            tool_name: Name of the tool to activate

        Returns:
            bool: True if activation successful
        """
        if tool_name not in self._registered_tools:
            logger.error(f"Tool '{tool_name}' not registered")
            return False

        # Create tool instance if needed
        if tool_name not in self._tool_instances:
            tool_class = self._registered_tools[tool_name]
            self._tool_instances[tool_name] = tool_class(tool_name, self.proj, self)
            self._connect_tool_signals(self._tool_instances[tool_name])

        tool = self._tool_instances[tool_name]

        # Set current image indices
        if self._primary_index is not None and self._secondary_index is not None:
            tool.set_image_indices(self._primary_index, self._secondary_index)

        # Activate the tool
        if tool.activate():
            self._active_tools[tool_name] = tool
            self._update_tool_panel()
            self.tool_activated.emit(tool_name)
            logger.info(f"Activated tool: {tool_name}")
            return True
        else:
            logger.error(f"Failed to activate tool: {tool_name}")
            return False

    def deactivate_tool(self, tool_name: str) -> bool:
        """
        Deactivate a specific tool.

        Args:
            tool_name: Name of the tool to deactivate

        Returns:
            bool: True if deactivation successful
        """
        if tool_name not in self._active_tools:
            logger.warning(f"Tool '{tool_name}' is not active")
            return True

        tool = self._active_tools[tool_name]

        if tool.deactivate():
            del self._active_tools[tool_name]
            self._update_tool_panel()
            self.tool_deactivated.emit(tool_name)
            logger.info(f"Deactivated tool: {tool_name}")
            return True
        else:
            logger.error(f"Failed to deactivate tool: {tool_name}")
            return False

    def deactivate_all_tools(self):
        """Deactivate all currently active viewport_tools"""
        tool_names = list(self._active_tools.keys())
        for tool_name in tool_names:
            self.deactivate_tool(tool_name)

    def handle_click(self, image_index: int, x: int, y: int, view_type: str) -> bool:
        """
        Route click events to active viewport_tools.

        Args:
            image_index: Index of the clicked image
            x, y: Click coordinates in image space
            view_type: Type of view ('primary' or 'secondary')

        Returns:
            bool: True if any tool handled the click
        """
        if not self._click_routing_enabled:
            return False

        handled = False

        # Route to all active viewport_tools (viewport_tools decide if they want to handle it)
        for tool_name, tool in self._active_tools.items():
            try:
                if tool.handle_click(image_index, x, y, view_type):
                    self.click_handled.emit(tool_name, image_index, x, y, view_type)
                    handled = True
                    logger.debug(f"Click handled by tool: {tool_name}")
            except Exception as e:
                logger.error(f"Error in tool '{tool_name}' click handler: {e}")

        return handled

    def set_image_indices(self, primary_index: int, secondary_index: int):
        """
        Update the current image pair for all viewport_tools.

        Args:
            primary_index: Index of primary image
            secondary_index: Index of secondary image
        """
        self._primary_index = primary_index
        self._secondary_index = secondary_index

        # Update all tool instances
        for tool in self._tool_instances.values():
            tool.set_image_indices(primary_index, secondary_index)

        logger.debug(
            f"Updated tool manager image indices: {primary_index}, {secondary_index}"
        )

    def get_tool_panel_widget(self) -> QWidget:
        """
        Get the widget containing all tool UI panels.

        Returns:
            QWidget: Container widget for tool panels
        """
        if self._tool_panel_widget is None:
            self._create_tool_panel_widget()

        return self._tool_panel_widget

    def set_click_routing_enabled(self, enabled: bool):
        """Enable or disable click event routing to viewport_tools"""
        self._click_routing_enabled = enabled
        logger.debug(f"Click routing {'enabled' if enabled else 'disabled'}")

    def get_registered_tools(self) -> List[str]:
        """Get list of all registered tool names"""
        return list(self._registered_tools.keys())

    def get_tool_info(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific tool"""
        if tool_name in self._tool_instances:
            return self._tool_instances[tool_name].get_tool_info()
        return None

    # Private methods

    def _create_tool_panel_widget(self):
        """Create the main tool panel widget"""
        self._tool_panel_widget = QWidget()
        layout = QVBoxLayout(self._tool_panel_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Create scroll area for tool panels
        self._tool_scroll_area = QScrollArea()
        self._tool_scroll_area.setWidgetResizable(True)
        self._tool_scroll_area.setHorizontalScrollBarPolicy(
            self._tool_scroll_area.horizontalScrollBarPolicy().ScrollBarAlwaysOff
        )

        # Container for tool panels
        self._tool_container = QWidget()
        self._tool_container_layout = QVBoxLayout(self._tool_container)
        self._tool_container_layout.setContentsMargins(0, 0, 0, 0)
        self._tool_container_layout.setSpacing(5)

        # Add stretch to push viewport_tools to top
        self._tool_container_layout.addStretch()

        self._tool_scroll_area.setWidget(self._tool_container)
        layout.addWidget(self._tool_scroll_area)

    def _update_tool_panel(self):
        """Update the tool panel to show/hide active tool UIs"""
        if self._tool_container_layout is None:
            return

        # Clear existing widgets
        self._clear_tool_container()

        # Add UI widgets for active viewport_tools
        for tool_name, tool in self._active_tools.items():
            ui_widget = tool.ui_widget
            if ui_widget:
                self._tool_container_layout.insertWidget(
                    self._tool_container_layout.count() - 1, ui_widget
                )

        logger.debug(
            f"Updated tool panel with {len(self._active_tools)} active viewport_tools"
        )

    def _clear_tool_container(self):
        """Clear all widgets from the tool container except the stretch"""
        layout = self._tool_container_layout
        while layout.count() > 1:  # Keep the stretch item
            item = layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)

    def _connect_tool_signals(self, tool: DualImageToolBase):
        """Connect signals from a tool instance"""
        tool.tool_activated.connect(self.tool_activated.emit)
        tool.tool_deactivated.connect(self.tool_deactivated.emit)
        tool.status_changed.connect(self._on_tool_status_changed)

    def _on_tool_status_changed(self, tool_name: str, status: str):
        """Handle tool status changes"""
        logger.debug(f"Tool '{tool_name}' status: {status}")
