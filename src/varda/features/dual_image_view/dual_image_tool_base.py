"""
Base classes for dual image view tools.

Provides the foundation for extensible tool architecture in dual image view.
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Tuple
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel

from varda.core.data import ProjectContext

logger = logging.getLogger(__name__)


class DualImageToolBase(QObject):
    """
    Abstract base class for dual image view tools.

    All dual image tools should inherit from this class to ensure
    consistent interface and integration with the tool manager.
    """

    # Signals
    tool_activated = pyqtSignal(str)  # tool_name
    tool_deactivated = pyqtSignal(str)  # tool_name
    status_changed = pyqtSignal(str, str)  # tool_name, status_message

    def __init__(self, tool_name: str, project_context: ProjectContext, parent=None):
        super().__init__(parent)
        self.tool_name = tool_name
        self.proj = project_context
        self._is_active = False
        self._primary_index: Optional[int] = None
        self._secondary_index: Optional[int] = None
        self._ui_widget: Optional[QWidget] = None

    @property
    def is_active(self) -> bool:
        """Check if tool is currently active"""
        return self._is_active

    @property
    def ui_widget(self) -> Optional[QWidget]:
        """Get the tool's UI widget"""
        return self._ui_widget

    def set_image_indices(self, primary_index: int, secondary_index: int):
        """Set the current image indices for the tool"""
        self._primary_index = primary_index
        self._secondary_index = secondary_index
        self._on_images_changed(primary_index, secondary_index)

    def activate(self) -> bool:
        """
        Activate the tool.

        Returns:
            bool: True if activation successful
        """
        if self._is_active:
            return True

        try:
            # Create UI if needed
            if self._ui_widget is None:
                self._ui_widget = self._create_ui()

            # Perform tool-specific activation
            if self._on_activate():
                self._is_active = True
                self.tool_activated.emit(self.tool_name)
                logger.debug(f"Tool '{self.tool_name}' activated")
                return True
            else:
                logger.error(f"Failed to activate tool '{self.tool_name}'")
                return False

        except Exception as e:
            logger.error(f"Error activating tool '{self.tool_name}': {e}")
            return False

    def deactivate(self) -> bool:
        """
        Deactivate the tool.

        Returns:
            bool: True if deactivation successful
        """
        if not self._is_active:
            return True

        try:
            # Perform tool-specific deactivation
            if self._on_deactivate():
                self._is_active = False
                self.tool_deactivated.emit(self.tool_name)
                logger.debug(f"Tool '{self.tool_name}' deactivated")
                return True
            else:
                logger.error(f"Failed to deactivate tool '{self.tool_name}'")
                return False

        except Exception as e:
            logger.error(f"Error deactivating tool '{self.tool_name}': {e}")
            return False

    def handle_click(self, image_index: int, x: int, y: int, view_type: str) -> bool:
        """
        Handle click events from either image view.

        Args:
            image_index: Index of the clicked image
            x, y: Click coordinates in image space
            view_type: Type of view that was clicked ('primary' or 'secondary')

        Returns:
            bool: True if click was handled by this tool
        """
        if not self._is_active:
            return False

        return self._on_click(image_index, x, y, view_type)

    # Abstract methods that subclasses must implement

    @abstractmethod
    def _create_ui(self) -> QWidget:
        """Create and return the tool's UI widget"""
        pass

    @abstractmethod
    def _on_activate(self) -> bool:
        """Handle tool activation logic"""
        pass

    @abstractmethod
    def _on_deactivate(self) -> bool:
        """Handle tool deactivation logic"""
        pass

    @abstractmethod
    def _on_click(self, image_index: int, x: int, y: int, view_type: str) -> bool:
        """Handle click events"""
        pass

    # Optional methods that subclasses can override

    def _on_images_changed(self, primary_index: int, secondary_index: int):
        """Called when the active image pair changes"""
        pass

    def get_tool_info(self) -> Dict[str, Any]:
        """Get information about this tool"""
        return {
            "name": self.tool_name,
            "active": self._is_active,
            "primary_index": self._primary_index,
            "secondary_index": self._secondary_index,
        }


class DualImageToolPanel(QWidget):
    """
    Base class for tool UI panels.

    Provides common UI structure and utilities for tool-specific controls.
    """

    def __init__(self, tool_name: str, parent=None):
        super().__init__(parent)
        self.tool_name = tool_name
        self._init_base_ui()

    def _init_base_ui(self):
        """Initialize the base UI structure"""
        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        self.main_layout.setSpacing(5)

        # Header section
        header_layout = QHBoxLayout()
        self.tool_label = QLabel(f"{self.tool_name} Tool")
        self.tool_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        header_layout.addWidget(self.tool_label)
        header_layout.addStretch()

        self.main_layout.addLayout(header_layout)

        # Content area for tool-specific controls
        self.content_layout = QVBoxLayout()
        self.main_layout.addLayout(self.content_layout)

        # Status area
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: gray; font-size: 10px;")
        self.main_layout.addWidget(self.status_label)

    def set_status(self, message: str):
        """Update the status message"""
        self.status_label.setText(message)

    def add_content_widget(self, widget: QWidget):
        """Add a widget to the content area"""
        self.content_layout.addWidget(widget)

    def add_content_layout(self, layout):
        """Add a layout to the content area"""
        self.content_layout.addLayout(layout)
