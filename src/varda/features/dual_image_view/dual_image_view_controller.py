"""
Dual Image View Controller

Coordinates dual image view operations, manages view state, and handles
user interactions for dual image functionality.
"""

import logging
from typing import Optional, Dict, Any, Tuple
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from PyQt6.QtWidgets import QWidget

from .dual_image_types import DualImageConfig, DualImageMode, LinkType
from .dual_image_link_manager import DualImageLinkManager
from .roi_sync_manager import ROISyncManager
from .overlay_manager import OverlayManager
from .blink_manager import BlinkManager
from varda.core.data import ProjectContext

logger = logging.getLogger(__name__)


class DualImageViewController(QObject):
    """
    Controller for dual image view functionality.

    Manages the interaction between dual image views, handles mode switching,
    and coordinates synchronization between linked images.
    """

    # Signals
    mode_changed = pyqtSignal(DualImageMode)  # Emitted when display mode changes
    overlay_opacity_changed = pyqtSignal(float)  # Emitted when overlay opacity changes
    blink_state_changed = pyqtSignal(bool)  # Emitted when blink state changes
    view_sync_requested = pyqtSignal(int, dict)  # target_index, sync_data
    crosshair_sync_requested = pyqtSignal(int, int, int)  # target_index, abs_x, abs_y
    dual_view_activated = pyqtSignal(int, int)  # primary_index, secondary_index
    dual_view_deactivated = pyqtSignal()

    def __init__(self, project_context: ProjectContext, parent=None):
        super().__init__(parent)
        self.proj = project_context

        # Initialize managers
        self.link_manager = DualImageLinkManager(project_context, self)
        self.roi_sync_manager = ROISyncManager(project_context, self)
        self.overlay_manager = OverlayManager(self)
        self.blink_manager = BlinkManager(self)

        # Current dual view state
        self._active_pair: Optional[Tuple[int, int]] = (
            None  # (primary_index, secondary_index)
        )
        self._current_config: Optional[DualImageConfig] = None
        self._is_dual_mode_active = False

        # View references
        self._primary_view: Optional[QWidget] = None
        self._secondary_view: Optional[QWidget] = None
        self._dual_view_widget: Optional[QWidget] = None

        # Blink timer
        self._blink_state = False  # True = primary visible, False = secondary visible

        # Sync state tracking
        self._sync_in_progress = False  # Prevent recursive sync calls

        # Connect signals
        self._connect_signals()
        self._connect_blink_signals()

    def activate_dual_view(
        self,
        primary_index: int,
        secondary_index: int,
        config: Optional[DualImageConfig] = None,
    ) -> bool:
        """
        Activate dual view mode for two images.

        Args:
            primary_index: Index of the primary image
            secondary_index: Index of the secondary image
            config: Configuration for the dual view (uses default if None)

        Returns:
            bool: True if dual view was activated successfully
        """
        if config is None:
            config = DualImageConfig()

        # Validate images exist
        if not self._validate_image_indices(primary_index, secondary_index):
            logger.error(f"Invalid image indices: {primary_index}, {secondary_index}")
            return False

        # Create or update link between images
        if not self.link_manager.create_link(primary_index, secondary_index, config):
            # Link might already exist, try to update config
            self.link_manager.update_link_config(primary_index, secondary_index, config)

        # NEW: Set up ROI synchronization
        if config.sync_rois:
            self.roi_sync_manager.setup_roi_sync(primary_index, secondary_index)

        # Store current state
        self._active_pair = (primary_index, secondary_index)
        self._current_config = config
        self._is_dual_mode_active = True

        # Set up views based on mode
        self._setup_dual_mode()

        logger.info(f"Activated dual view: {primary_index} <-> {secondary_index}")
        self.dual_view_activated.emit(primary_index, secondary_index)
        return True

    def deactivate_dual_view(self) -> bool:
        """
        Deactivate dual view mode and return to single image view.

        Returns:
            bool: True if dual view was deactivated successfully
        """
        if not self._is_dual_mode_active:
            return True

        # Clean up all managers
        self.blink_manager.cleanup_blink()
        self.overlay_manager.cleanup_overlay()

        # Clean up ROI synchronization
        if self._active_pair:
            self.roi_sync_manager.cleanup_roi_sync(
                self._active_pair[0], self._active_pair[1]
            )

        # Reset state
        self._active_pair = None
        self._current_config = None
        self._is_dual_mode_active = False
        self._primary_view = None
        self._secondary_view = None

        logger.info("Deactivated dual view mode")
        self.dual_view_deactivated.emit()
        return True

    def set_display_mode(self, mode: DualImageMode) -> bool:
        """Change the display mode for the current dual view"""
        if not self._is_dual_mode_active or not self._current_config:
            return False

        old_mode = self._current_config.mode
        self._current_config.mode = mode

        # Update the link configuration
        if self._active_pair:
            self.link_manager.update_link_config(
                self._active_pair[0], self._active_pair[1], self._current_config
            )

        # Handle mode-specific setup
        self._setup_dual_mode()

        logger.info(f"Changed display mode from {old_mode} to {mode}")
        self.mode_changed.emit(mode)
        return True

    def set_overlay_opacity(self, opacity: float) -> bool:
        """Set the opacity for overlay mode"""
        if not self._is_dual_mode_active or not self._current_config:
            return False

        # Clamp opacity to valid range
        opacity = max(0.0, min(1.0, opacity))
        self._current_config.overlay_opacity = opacity

        # Update link configuration
        if self._active_pair:
            self.link_manager.update_link_config(
                self._active_pair[0], self._active_pair[1], self._current_config
            )

        # Apply opacity through overlay manager
        success = self.overlay_manager.set_overlay_opacity(opacity)

        if success:
            self.overlay_opacity_changed.emit(opacity)

        return success

    def toggle_blink(self) -> bool:
        """Toggle blink mode on/off"""
        if not self._is_dual_mode_active or not self._current_config:
            return False

        # Use blink manager to toggle
        new_state = self.blink_manager.toggle_blink()

        # Update configuration
        self._current_config.blink_enabled = new_state

        # Update link configuration
        if self._active_pair:
            self.link_manager.update_link_config(
                self._active_pair[0], self._active_pair[1], self._current_config
            )

        self.blink_state_changed.emit(new_state)
        return new_state

    def set_blink_interval(self, interval_ms: int) -> bool:
        """Set the blink interval in milliseconds"""
        if not self._is_dual_mode_active or not self._current_config:
            return False

        # Update configuration
        self._current_config.blink_interval = max(50, interval_ms)

        # Apply through blink manager
        success = self.blink_manager.set_blink_interval(
            self._current_config.blink_interval
        )

        return success

    def is_blinking(self) -> bool:
        """Check if currently blinking"""
        return self.blink_manager.is_blink_active()

    def step_blink(self):
        """Manually step to next blink frame"""
        self.blink_manager.step_blink()

    def set_view_references(self, primary_view: QWidget, secondary_view: QWidget):
        """Set references to the primary and secondary view widgets"""
        self._primary_view = primary_view
        self._secondary_view = secondary_view

        logger.debug(
            f"View references set: primary={primary_view is not None}, secondary={secondary_view is not None}"
        )

        # Update all managers with the new view references
        if self._current_config:
            mode = self._current_config.mode

            if mode == DualImageMode.OVERLAY:
                self.overlay_manager.setup_overlay(primary_view, secondary_view)
                self.overlay_manager.set_overlay_opacity(
                    self._current_config.overlay_opacity
                )
            elif mode == DualImageMode.BLINK:
                self.blink_manager.setup_blink(primary_view, secondary_view)
                if self._current_config.blink_enabled:
                    self.blink_manager.start_blink()

            logger.debug(f"Managers updated for mode: {mode}")

    def sync_navigation(self, source_index: int, view_state: Dict[str, Any]):
        """
        Synchronize navigation between linked views with improved precision.

        Args:
            source_index: Index of the image that triggered the navigation change
            view_state: Dictionary containing view state (zoom, pan, etc.)
        """
        if (
            self._sync_in_progress
            or not self._is_dual_mode_active
            or not self._active_pair
            or not self._current_config.sync_navigation
        ):
            return

        # Find target index
        target_index = None
        if source_index == self._active_pair[0]:
            target_index = self._active_pair[1]
        elif source_index == self._active_pair[1]:
            target_index = self._active_pair[0]
        else:
            return  # Not part of active pair

        logger.debug(f"Syncing navigation from {source_index} to {target_index}")

        # Transform coordinates if needed - preserve precision during transformation
        transformed_state = self._transform_view_state(
            source_index, target_index, view_state
        )

        # Prevent recursive sync - use immediate flag setting
        self._sync_in_progress = True

        try:
            self.view_sync_requested.emit(target_index, transformed_state)
            logger.debug(f"Emitted sync request for index {target_index}")
        except Exception as e:
            logger.error(f"Error emitting sync request: {e}")
        finally:
            # Reset sync flag immediately instead of using timer
            self._sync_in_progress = False

    def sync_roi(self, source_index: int, roi_id: str):
        """Synchronize ROI between linked views"""
        if (
            not self._is_dual_mode_active
            or not self._active_pair
            or not self._current_config.sync_rois
        ):
            return

        # Find target index
        target_index = None
        if source_index == self._active_pair[0]:
            target_index = self._active_pair[1]
        elif source_index == self._active_pair[1]:
            target_index = self._active_pair[0]
        else:
            return  # Not part of active pair

        # Sync the ROI
        success = self.roi_sync_manager.sync_roi(roi_id, source_index, target_index)
        if success:
            logger.debug(
                f"Successfully synced ROI {roi_id} from {source_index} to {target_index}"
            )
        else:
            logger.warning(
                f"Failed to sync ROI {roi_id} from {source_index} to {target_index}"
            )

    def sync_crosshair(
        self, source_index: int, zoom_x: int, zoom_y: int, abs_x: int, abs_y: int
    ):
        """
        Synchronize crosshair position between linked views.

        Args:
            source_index: Index of the image that triggered the crosshair change
            zoom_x, zoom_y: Crosshair position in zoom view coordinates
            abs_x, abs_y: Crosshair position in absolute image coordinates
        """
        if (
            not self._is_dual_mode_active
            or not self._active_pair
            or not self._current_config.sync_navigation
        ):
            return

        # Find target index
        target_index = None
        if source_index == self._active_pair[0]:
            target_index = self._active_pair[1]
        elif source_index == self._active_pair[1]:
            target_index = self._active_pair[0]
        else:
            return  # Not part of active pair

        logger.debug(
            f"Syncing crosshair from {source_index} to {target_index} at abs coords ({abs_x}, {abs_y})"
        )

        # Transform coordinates if needed for geospatial linking
        if self._current_config.link_type == LinkType.PIXEL_BASED:
            # For pixel-based linking, use coordinates directly
            transformed_abs_x, transformed_abs_y = abs_x, abs_y
        else:
            # For geospatial linking, transform coordinates
            transformed_coords = self.link_manager.transform_coordinates(
                source_index, target_index, abs_x, abs_y
            )
            if transformed_coords:
                transformed_abs_x, transformed_abs_y = transformed_coords
            else:
                logger.warning("Failed to transform crosshair coordinates")
                return

        # Emit sync request
        try:
            self.crosshair_sync_requested.emit(
                target_index, transformed_abs_x, transformed_abs_y
            )
            logger.debug(f"Emitted crosshair sync request for index {target_index}")
        except Exception as e:
            logger.error(f"Error emitting crosshair sync request: {e}")

    def get_current_config(self) -> Optional[DualImageConfig]:
        """Get the current dual view configuration"""
        return self._current_config

    def get_active_pair(self) -> Optional[Tuple[int, int]]:
        """Get the currently active image pair"""
        return self._active_pair

    def is_dual_mode_active(self) -> bool:
        """Check if dual view mode is currently active"""
        return self._is_dual_mode_active

    # Private methods

    def _connect_signals(self):
        """Connect internal signals"""
        self.link_manager.navigation_sync_requested.connect(
            self._handle_navigation_sync
        )
        self.link_manager.roi_sync_requested.connect(self._handle_roi_sync)

    def _connect_blink_signals(self):
        """Connect blink manager signals"""
        self.blink_manager.blink_state_changed.connect(self._on_blink_state_changed)
        self.blink_manager.blink_started.connect(
            lambda: self.blink_state_changed.emit(True)
        )
        self.blink_manager.blink_stopped.connect(
            lambda: self.blink_state_changed.emit(False)
        )

    def _setup_dual_mode(self):
        """Setup the dual view based on current configuration"""
        if (
            not self._current_config
            or not self._primary_view
            or not self._secondary_view
        ):
            logger.warning(
                f"Cannot setup dual mode - config={self._current_config is not None}, primary={self._primary_view is not None}, secondary={self._secondary_view is not None}"
            )
            return

        mode = self._current_config.mode
        logger.debug(f"Setting up dual mode: {mode}")

        if mode == DualImageMode.SIDE_BY_SIDE:
            self._setup_side_by_side_mode()
        elif mode == DualImageMode.OVERLAY:
            self._setup_overlay_mode()
        elif mode == DualImageMode.BLINK:
            self._setup_blink_mode()

    def _setup_side_by_side_mode(self):
        """Setup side-by-side display mode"""
        # Stop any active managers
        self.blink_manager.stop_blink()
        self.overlay_manager.cleanup_overlay()

        # Show both views normally - both are equal primary views in side-by-side mode
        if self._primary_view:
            self._primary_view.setVisible(True)
            if hasattr(self._primary_view, "set_dual_mode"):
                self._primary_view.set_dual_mode(True, False)  # Primary view

        if self._secondary_view:
            self._secondary_view.setVisible(True)
            if hasattr(self._secondary_view, "set_dual_mode"):
                self._secondary_view.set_dual_mode(
                    True, False
                )  # Also primary, not overlay

        logger.debug("Side-by-side mode setup complete")

    def _setup_overlay_mode(self):
        """Setup overlay display mode"""
        # Stop any active blinking
        self.blink_manager.stop_blink()

        # Set up overlay using overlay manager
        if self._primary_view and self._secondary_view:
            success = self.overlay_manager.setup_overlay(
                self._primary_view, self._secondary_view
            )
            if success:
                # Apply current opacity setting
                self.overlay_manager.set_overlay_opacity(
                    self._current_config.overlay_opacity
                )
                logger.debug("Overlay mode activated")
            else:
                logger.error("Failed to set up overlay mode")

    def _setup_blink_mode(self):
        """Setup blink display mode"""
        # Clean up overlay
        self.overlay_manager.cleanup_overlay()

        # Set up blink using blink manager
        if self._primary_view and self._secondary_view:
            success = self.blink_manager.setup_blink(
                self._primary_view, self._secondary_view
            )
            if success:
                # Apply current settings
                self.blink_manager.set_blink_interval(
                    self._current_config.blink_interval
                )

                # Start blinking if enabled
                if self._current_config and self._current_config.blink_enabled:
                    self.blink_manager.start_blink()

                logger.debug("Blink mode activated")
            else:
                logger.error("Failed to set up blink mode")
        else:
            logger.error(
                f"Cannot setup blink - views missing: primary={self._primary_view is not None}, secondary={self._secondary_view is not None}"
            )

    def _start_blinking(self):
        """Start the blink timer"""
        if self._current_config:
            return self.blink_manager.start_blink()
        return False

    def _stop_blinking(self):
        """Stop the blink timer"""
        return self.blink_manager.stop_blink()

    def _on_blink_state_changed(self, primary_visible: bool):
        """Handle blink state changes from blink manager"""
        logger.debug(f"Blink state changed: primary_visible={primary_visible}")
        # Additional handling can be added here if needed

    def _update_blink_visibility(self):
        """Update view visibility for blink mode"""
        if self._primary_view and self._secondary_view:
            if self._blink_state:
                self._primary_view.setVisible(True)
                self._secondary_view.setVisible(False)
            else:
                self._primary_view.setVisible(False)
                self._secondary_view.setVisible(True)

    def _apply_overlay_opacity(self):
        """Apply overlay opacity to secondary view"""
        if self._secondary_view and self._current_config:
            # This would need to be implemented based on the specific view widget type
            # For now, we'll emit a signal that the view can handle
            opacity = self._current_config.overlay_opacity
            logger.debug(f"Applying overlay opacity: {opacity}")
            # The actual implementation would depend on the view widget's API

    def _transform_view_state(
        self, source_index: int, target_index: int, view_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Transform view state coordinates between images with precision preservation.

        Args:
            source_index: Index of source image
            target_index: Index of target image
            view_state: View state to transform

        Returns:
            Transformed view state
        """
        # For pixel-based linking, preserve exact coordinates without transformation
        if self._current_config.link_type == LinkType.PIXEL_BASED:
            # Create a deep copy to avoid modifying original state
            transformed_state = {}
            for key, value in view_state.items():
                if isinstance(value, list):
                    # Preserve coordinate precision for position/size arrays
                    transformed_state[key] = value.copy()
                else:
                    transformed_state[key] = value
            return transformed_state

        # For geospatial linking, apply coordinate transformation while preserving precision
        transformed_state = view_state.copy()

        # Transform coordinates if present
        if (
            "pos" in view_state
            and isinstance(view_state["pos"], list)
            and len(view_state["pos"]) == 2
        ):
            transformed_coords = self.link_manager.transform_coordinates(
                source_index, target_index, view_state["pos"][0], view_state["pos"][1]
            )
            if transformed_coords:
                # Preserve precision in transformed coordinates
                transformed_state["pos"] = [
                    transformed_coords[0],
                    transformed_coords[1],
                ]

        # Transform size if present and needed for geospatial
        if (
            "size" in view_state
            and isinstance(view_state["size"], list)
            and len(view_state["size"]) == 2
        ):
            # For size, we might need to transform the scale/resolution
            # For now, preserve original size unless specific transformation is needed
            transformed_state["size"] = view_state["size"].copy()

        return transformed_state

    def _handle_navigation_sync(self, target_index: int, transform_data: Any):
        """Handle navigation sync requests from link manager"""
        # Convert transform_data to view state format
        view_state = {}
        if hasattr(transform_data, "__dict__"):
            view_state = transform_data.__dict__
        elif isinstance(transform_data, dict):
            view_state = transform_data

        self.view_sync_requested.emit(target_index, view_state)

    def _handle_roi_sync(self, target_index: int, roi_id: str):
        """Handle ROI sync requests from link manager"""
        # This would trigger ROI synchronization in the target view
        logger.debug(f"Syncing ROI {roi_id} to image {target_index}")
        # Implementation depends on ROI management system

    def _validate_image_indices(self, index1: int, index2: int) -> bool:
        """Validate that image indices are valid"""
        try:
            images = self.proj.getAllImages()
            return 0 <= index1 < len(images) and 0 <= index2 < len(images)
        except Exception as e:
            logger.error(f"Error validating image indices: {e}")
            return False
