"""
Blink Manager

Manages blink functionality for dual image view, alternating between two images
at a specified interval to help users spot differences.
"""

import logging
from typing import Optional
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from PyQt6.QtWidgets import QWidget

logger = logging.getLogger(__name__)


class BlinkManager(QObject):
    """
    Manages blink functionality for dual image views.
    
    Handles:
    - Alternating visibility between two views
    - Configurable blink timing
    - Smooth transitions
    - Blink state management
    """
    
    # Signals
    blink_state_changed = pyqtSignal(bool)  # True = primary visible, False = secondary visible
    blink_started = pyqtSignal()
    blink_stopped = pyqtSignal()
    blink_interval_changed = pyqtSignal(int)  # new interval in ms
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Blink state
        self._blink_active = False
        self._blink_interval = 1000  # milliseconds
        self._current_state = True  # True = primary visible, False = secondary visible
        
        # View references
        self._primary_view: Optional[QWidget] = None
        self._secondary_view: Optional[QWidget] = None
        
        # Blink timer
        self._blink_timer = QTimer(self)
        self._blink_timer.timeout.connect(self._on_blink_timer)
        self._blink_timer.setSingleShot(False)
        
        # Fade effect settings (for future enhancement)
        self._use_fade_effect = False
        self._fade_duration = 100  # milliseconds
        
    def setup_blink(self, primary_view: QWidget, secondary_view: QWidget) -> bool:
        """
        Set up blink mode between two views.
        
        Args:
            primary_view: The primary raster view
            secondary_view: The secondary raster view
            
        Returns:
            bool: True if blink was set up successfully
        """
        try:
            self._primary_view = primary_view
            self._secondary_view = secondary_view
            
            if not self._primary_view or not self._secondary_view:
                logger.error("Invalid views provided for blink setup")
                return False
            
            # Configure both views for blink mode
            if hasattr(self._primary_view, 'set_dual_mode'):
                self._primary_view.set_dual_mode(True, False)
            
            if hasattr(self._secondary_view, 'set_dual_mode'):
                self._secondary_view.set_dual_mode(True, False)
            
            # Set initial state (primary visible)
            self._set_blink_visibility_state(True)
            
            logger.debug("Blink mode set up successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error setting up blink mode: {e}")
            return False
    
    def cleanup_blink(self):
        """Clean up blink mode"""
        try:
            # Stop blinking
            self.stop_blink()
            
            # Reset views to normal mode
            if self._primary_view and hasattr(self._primary_view, 'set_dual_mode'):
                self._primary_view.set_dual_mode(False)
            
            if self._secondary_view and hasattr(self._secondary_view, 'set_dual_mode'):
                self._secondary_view.set_dual_mode(False)
            
            # Make both views visible
            if self._primary_view:
                self._primary_view.setVisible(True)
            if self._secondary_view:
                self._secondary_view.setVisible(True)
            
            self._primary_view = None
            self._secondary_view = None
            
            logger.debug("Blink mode cleaned up")
            
        except Exception as e:
            logger.error(f"Error cleaning up blink mode: {e}")
    
    def start_blink(self) -> bool:
        """
        Start blinking between the two views.
        
        Returns:
            bool: True if blinking started successfully
        """
        try:
            if not self._primary_view or not self._secondary_view:
                logger.error("Cannot start blink - views not set up")
                return False
            
            if self._blink_active:
                logger.debug("Blink already active")
                return True
            
            # Set initial state (primary visible)
            self._current_state = True
            self._set_blink_visibility_state(self._current_state)
            
            # Start the timer
            self._blink_timer.setInterval(self._blink_interval)
            self._blink_timer.start()
            
            self._blink_active = True
            self.blink_started.emit()
            
            logger.debug(f"Blink started with interval {self._blink_interval}ms")
            return True
            
        except Exception as e:
            logger.error(f"Error starting blink: {e}")
            return False
    
    def stop_blink(self) -> bool:
        """
        Stop blinking and show both views.
        
        Returns:
            bool: True if blinking stopped successfully
        """
        try:
            if not self._blink_active:
                return True
            
            # Stop the timer
            self._blink_timer.stop()
            
            # Show both views
            if self._primary_view:
                self._primary_view.setVisible(True)
            if self._secondary_view:
                self._secondary_view.setVisible(True)
            
            self._blink_active = False
            self.blink_stopped.emit()
            
            logger.debug("Blink stopped")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping blink: {e}")
            return False
    
    def toggle_blink(self) -> bool:
        """
        Toggle blink on/off.
        
        Returns:
            bool: New blink state (True = blinking, False = not blinking)
        """
        if self._blink_active:
            self.stop_blink()
            return False
        else:
            self.start_blink()
            return True
    
    def set_blink_interval(self, interval_ms: int) -> bool:
        """
        Set the blink interval.
        
        Args:
            interval_ms: Blink interval in milliseconds (minimum 50ms)
            
        Returns:
            bool: True if interval was set successfully
        """
        try:
            # Clamp to reasonable range
            interval_ms = max(50, min(10000, interval_ms))
            
            old_interval = self._blink_interval
            self._blink_interval = interval_ms
            
            # Update timer if currently active
            if self._blink_active and self._blink_timer.isActive():
                self._blink_timer.setInterval(self._blink_interval)
            
            if old_interval != interval_ms:
                self.blink_interval_changed.emit(interval_ms)
                logger.debug(f"Blink interval set to {interval_ms}ms")
            
            return True
            
        except Exception as e:
            logger.error(f"Error setting blink interval: {e}")
            return False
    
    def get_blink_interval(self) -> int:
        """Get the current blink interval in milliseconds"""
        return self._blink_interval
    
    def is_blink_active(self) -> bool:
        """Check if blinking is currently active"""
        return self._blink_active
    
    def get_current_visible_view(self) -> Optional[QWidget]:
        """Get the currently visible view during blinking"""
        if not self._blink_active:
            return None
        
        return self._primary_view if self._current_state else self._secondary_view
    
    def force_show_primary(self):
        """Force show primary view (useful for manual control)"""
        if self._blink_active:
            self._current_state = True
            self._set_blink_visibility_state(True)
    
    def force_show_secondary(self):
        """Force show secondary view (useful for manual control)"""
        if self._blink_active:
            self._current_state = False
            self._set_blink_visibility_state(False)
    
    def step_blink(self):
        """Manually step to next blink state (useful for frame-by-frame analysis)"""
        if self._primary_view and self._secondary_view:
            self._current_state = not self._current_state
            self._set_blink_visibility_state(self._current_state)
    
    def set_fade_effect(self, enabled: bool, duration_ms: int = 100):
        """
        Enable/disable fade effect during blink transitions (future enhancement).
        
        Args:
            enabled: Whether to use fade effect
            duration_ms: Duration of fade transition in milliseconds
        """
        self._use_fade_effect = enabled
        self._fade_duration = max(10, min(500, duration_ms))
        logger.debug(f"Fade effect {'enabled' if enabled else 'disabled'} with duration {self._fade_duration}ms")
    
    # Private methods
    
    def _on_blink_timer(self):
        """Handle blink timer timeout"""
        try:
            # Toggle visibility state
            self._current_state = not self._current_state
            self._set_blink_visibility_state(self._current_state)
            
            # Emit state change
            self.blink_state_changed.emit(self._current_state)
            
        except Exception as e:
            logger.error(f"Error in blink timer handler: {e}")
    
    def _set_blink_visibility_state(self, primary_visible: bool):
        """
        Set the visibility state for blink mode.
        
        Args:
            primary_visible: True to show primary, False to show secondary
        """
        try:
            if primary_visible:
                # Show primary, hide secondary
                if self._primary_view:
                    self._primary_view.setVisible(True)
                if self._secondary_view:
                    self._secondary_view.setVisible(False)
            else:
                # Hide primary, show secondary
                if self._primary_view:
                    self._primary_view.setVisible(False)
                if self._secondary_view:
                    self._secondary_view.setVisible(True)
            
            # Optional: Add fade effect here in the future
            if self._use_fade_effect:
                self._apply_fade_effect(primary_visible)
                
        except Exception as e:
            logger.error(f"Error setting blink visibility state: {e}")
    
    def _apply_fade_effect(self, primary_visible: bool):
        """
        Apply fade effect during transition (placeholder for future enhancement).
        
        Args:
            primary_visible: Target visibility state
        """
        # This would implement smooth fade transitions using QGraphicsOpacityEffect
        # or custom animation framework
        logger.debug(f"Fade effect applied (placeholder): primary_visible={primary_visible}")