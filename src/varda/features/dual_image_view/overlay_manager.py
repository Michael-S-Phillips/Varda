"""
Overlay Manager

Manages overlay functionality for dual image view, including transparency controls
and overlay positioning.
"""

import logging
from typing import Optional, Tuple
import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QWidget

logger = logging.getLogger(__name__)


class OverlayManager(QObject):
    """
    Manages overlay functionality for dual image views.
    
    Handles:
    - Overlay positioning and alignment
    - Transparency/opacity control
    - Blend mode management
    - Overlay visibility management
    """
    
    # Signals
    overlay_updated = pyqtSignal(float)  # opacity
    overlay_visibility_changed = pyqtSignal(bool)  # visible
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Overlay state
        self._overlay_active = False
        self._overlay_opacity = 0.5
        self._primary_view = None
        self._secondary_view = None
        self._overlay_widget = None
        
        # Overlay positioning
        self._overlay_offset = (0, 0)  # x, y offset for overlay alignment
        self._overlay_scale = 1.0  # scale factor for overlay
        
    def setup_overlay(self, primary_view: QWidget, secondary_view: QWidget) -> bool:
        """
        Set up overlay mode between two views.
        
        Args:
            primary_view: The primary (background) raster view
            secondary_view: The secondary (overlay) raster view
            
        Returns:
            bool: True if overlay was set up successfully
        """
        try:
            self._primary_view = primary_view
            self._secondary_view = secondary_view
            
            if not self._primary_view or not self._secondary_view:
                logger.error("Invalid views provided for overlay setup")
                return False
            
            # Configure primary view as background
            if hasattr(self._primary_view, 'set_dual_mode'):
                self._primary_view.set_dual_mode(True, False)  # Primary, not overlay
            
            # Configure secondary view as overlay
            if hasattr(self._secondary_view, 'set_dual_mode'):
                self._secondary_view.set_dual_mode(True, True)  # Secondary, is overlay
            
            # Set initial opacity
            self.set_overlay_opacity(self._overlay_opacity)
            
            # Set up overlay positioning
            self._setup_overlay_positioning()
            
            self._overlay_active = True
            logger.debug("Overlay mode set up successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error setting up overlay: {e}")
            return False
    
    def cleanup_overlay(self):
        """Clean up overlay mode"""
        try:
            if self._primary_view and hasattr(self._primary_view, 'set_dual_mode'):
                self._primary_view.set_dual_mode(False)
            
            if self._secondary_view and hasattr(self._secondary_view, 'set_dual_mode'):
                self._secondary_view.set_dual_mode(False)
            
            self._overlay_active = False
            self._primary_view = None
            self._secondary_view = None
            
            logger.debug("Overlay mode cleaned up")
            
        except Exception as e:
            logger.error(f"Error cleaning up overlay: {e}")
    
    def set_overlay_opacity(self, opacity: float) -> bool:
        """
        Set the opacity of the overlay.
        
        Args:
            opacity: Opacity value between 0.0 (transparent) and 1.0 (opaque)
            
        Returns:
            bool: True if opacity was set successfully
        """
        try:
            # Clamp opacity to valid range
            opacity = max(0.0, min(1.0, opacity))
            self._overlay_opacity = opacity
            
            # Apply opacity to secondary view
            if self._secondary_view and hasattr(self._secondary_view, 'set_overlay_opacity'):
                self._secondary_view.set_overlay_opacity(opacity)
            elif self._secondary_view:
                # Fallback: try to set widget opacity
                if hasattr(self._secondary_view, 'setWindowOpacity'):
                    self._secondary_view.setWindowOpacity(opacity)
                elif hasattr(self._secondary_view, 'setOpacity'):
                    self._secondary_view.setOpacity(opacity)
            
            self.overlay_updated.emit(opacity)
            logger.debug(f"Overlay opacity set to {opacity}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting overlay opacity: {e}")
            return False
    
    def get_overlay_opacity(self) -> float:
        """Get the current overlay opacity"""
        return self._overlay_opacity
    
    def set_overlay_visibility(self, visible: bool):
        """
        Set overlay visibility.
        
        Args:
            visible: Whether the overlay should be visible
        """
        try:
            if self._secondary_view:
                if visible and self._overlay_active:
                    self._secondary_view.setVisible(True)
                    # Restore opacity
                    self.set_overlay_opacity(self._overlay_opacity)
                else:
                    self._secondary_view.setVisible(False)
            
            self.overlay_visibility_changed.emit(visible)
            
        except Exception as e:
            logger.error(f"Error setting overlay visibility: {e}")
    
    def is_overlay_active(self) -> bool:
        """Check if overlay mode is currently active"""
        return self._overlay_active
    
    def align_overlay(self, alignment: str = "center") -> bool:
        """
        Align the overlay with the primary view.
        
        Args:
            alignment: Alignment mode ("center", "top-left", "top-right", "bottom-left", "bottom-right")
            
        Returns:
            bool: True if alignment was successful
        """
        try:
            if not self._overlay_active or not self._primary_view or not self._secondary_view:
                return False
            
            # Get view dimensions
            primary_size = self._primary_view.size()
            secondary_size = self._secondary_view.size()
            
            # Calculate offset based on alignment
            offset_x, offset_y = self._calculate_alignment_offset(
                alignment, primary_size, secondary_size
            )
            
            self._overlay_offset = (offset_x, offset_y)
            
            # Apply positioning
            self._apply_overlay_positioning()
            
            logger.debug(f"Overlay aligned with mode: {alignment}")
            return True
            
        except Exception as e:
            logger.error(f"Error aligning overlay: {e}")
            return False
    
    def set_overlay_offset(self, x_offset: int, y_offset: int):
        """
        Set manual offset for overlay positioning.
        
        Args:
            x_offset: Horizontal offset in pixels
            y_offset: Vertical offset in pixels
        """
        self._overlay_offset = (x_offset, y_offset)
        self._apply_overlay_positioning()
    
    def get_overlay_offset(self) -> Tuple[int, int]:
        """Get the current overlay offset"""
        return self._overlay_offset
    
    def toggle_overlay_visibility(self) -> bool:
        """
        Toggle overlay visibility.
        
        Returns:
            bool: New visibility state
        """
        if self._secondary_view:
            current_visible = self._secondary_view.isVisible()
            new_visible = not current_visible
            self.set_overlay_visibility(new_visible)
            return new_visible
        return False
    
    # Private methods
    
    def _setup_overlay_positioning(self):
        """Set up initial overlay positioning"""
        try:
            if not self._primary_view or not self._secondary_view:
                return
            
            # Default to center alignment
            self.align_overlay("center")
            
        except Exception as e:
            logger.error(f"Error setting up overlay positioning: {e}")
    
    def _calculate_alignment_offset(self, alignment: str, primary_size, secondary_size) -> Tuple[int, int]:
        """Calculate offset for specified alignment"""
        primary_width = primary_size.width()
        primary_height = primary_size.height()
        secondary_width = secondary_size.width()
        secondary_height = secondary_size.height()
        
        if alignment == "center":
            offset_x = (primary_width - secondary_width) // 2
            offset_y = (primary_height - secondary_height) // 2
        elif alignment == "top-left":
            offset_x = 0
            offset_y = 0
        elif alignment == "top-right":
            offset_x = primary_width - secondary_width
            offset_y = 0
        elif alignment == "bottom-left":
            offset_x = 0
            offset_y = primary_height - secondary_height
        elif alignment == "bottom-right":
            offset_x = primary_width - secondary_width
            offset_y = primary_height - secondary_height
        else:
            # Default to center
            offset_x = (primary_width - secondary_width) // 2
            offset_y = (primary_height - secondary_height) // 2
        
        return (offset_x, offset_y)
    
    def _apply_overlay_positioning(self):
        """Apply the current overlay positioning"""
        try:
            if not self._secondary_view or not self._overlay_active:
                return
            
            offset_x, offset_y = self._overlay_offset
            
            # Move the secondary view to create overlay effect
            if hasattr(self._secondary_view, 'move'):
                self._secondary_view.move(offset_x, offset_y)
            
        except Exception as e:
            logger.error(f"Error applying overlay positioning: {e}")