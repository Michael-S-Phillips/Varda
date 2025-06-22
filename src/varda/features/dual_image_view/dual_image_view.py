"""
Dual Image View Widget

Main widget for displaying two images side-by-side with dual view controls
and synchronization capabilities.
"""

import logging
from typing import Optional, Dict, Any
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QSplitter,
    QGroupBox,
    QPushButton,
    QSlider,
    QLabel,
    QComboBox,
    QCheckBox,
    QSpinBox,
    QFrame,
    QToolBar,
    QSizePolicy,
)
from PyQt6.QtGui import QAction, QIcon

from .dual_image_types import DualImageMode, LinkType, DualImageConfig
from .dual_image_view_controller import DualImageViewController
from varda.features.image_view_raster.raster_view import RasterView
from varda.core.data import ProjectContext

logger = logging.getLogger(__name__)


class DualImageView(QWidget):
    """
    Widget for displaying two images side-by-side with dual view functionality.

    Provides controls for:
    - Linking/unlinking images
    - Switching between display modes (side-by-side, overlay, blink)
    - Adjusting overlay opacity
    - Controlling blink timing
    - Synchronization settings
    """

    # Signals
    primary_image_changed = pyqtSignal(
        int
    )  # Emitted when primary image selection changes
    secondary_image_changed = pyqtSignal(int)  # Emitted when secondary image changes
    link_toggled = pyqtSignal(bool)  # Emitted when link is toggled on/off

    def __init__(self, project_context: ProjectContext, parent=None):
        super().__init__(parent)
        self.proj = project_context

        # Initialize controller
        self.controller = DualImageViewController(project_context, self)

        # State tracking
        self._primary_index: Optional[int] = None
        self._secondary_index: Optional[int] = None
        self._raster_views: Dict[int, RasterView] = {}  # image_index -> RasterView
        self._is_linked = False

        # UI components
        self.primary_view_container = None
        self.secondary_view_container = None
        self.control_panel = None
        self.splitter = None

        # Control widgets
        self.mode_combo = None
        self.opacity_slider = None
        self.opacity_label = None
        self.blink_button = None
        self.blink_interval_spin = None
        self.link_button = None
        self.sync_navigation_cb = None
        self.sync_rois_cb = None

        # Initialize UI
        self._init_ui()
        self._connect_signals()

        logger.debug("DualImageView initialized")

    def _init_ui(self):
        """Initialize the user interface"""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        # Control panel
        self.control_panel = self._create_control_panel()
        main_layout.addWidget(self.control_panel)

        # Image view splitter
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        # Primary view container
        self.primary_view_container = self._create_view_container("Primary Image")
        self.splitter.addWidget(self.primary_view_container)

        # Secondary view container
        self.secondary_view_container = self._create_view_container("Secondary Image")
        self.splitter.addWidget(self.secondary_view_container)

        # Set equal split
        self.splitter.setSizes([400, 400])

        main_layout.addWidget(self.splitter)

        # Initially disable controls
        self._update_control_states()

    def _create_control_panel(self) -> QGroupBox:
        """Create the dual view control panel"""
        panel = QGroupBox("Dual View Controls")
        layout = QHBoxLayout(panel)

        # Link controls
        link_group = self._create_link_controls()
        layout.addWidget(link_group)

        # Separator
        separator1 = QFrame()
        separator1.setFrameShape(QFrame.Shape.VLine)
        separator1.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator1)

        # Display mode controls
        mode_group = self._create_mode_controls()
        layout.addWidget(mode_group)

        # Separator
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.Shape.VLine)
        separator2.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator2)

        # Overlay controls
        overlay_group = self._create_overlay_controls()
        layout.addWidget(overlay_group)

        # Separator
        separator3 = QFrame()
        separator3.setFrameShape(QFrame.Shape.VLine)
        separator3.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator3)

        # Blink controls
        blink_group = self._create_blink_controls()
        layout.addWidget(blink_group)

        # Separator
        separator4 = QFrame()
        separator4.setFrameShape(QFrame.Shape.VLine)
        separator4.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator4)

        # Sync controls
        sync_group = self._create_sync_controls()
        layout.addWidget(sync_group)

        # Stretch to fill available space
        layout.addStretch()

        return panel

    def _create_link_controls(self) -> QWidget:
        """Create link/unlink controls"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)

        # Link button
        self.link_button = QPushButton("Link Images")
        self.link_button.setCheckable(True)
        self.link_button.setToolTip(
            "Link/unlink the two images for synchronized viewing"
        )
        self.link_button.clicked.connect(self._toggle_link)
        layout.addWidget(self.link_button)

        return widget

    def _create_mode_controls(self) -> QWidget:
        """Create display mode controls"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)

        # Mode selection
        layout.addWidget(QLabel("Display Mode:"))
        self.mode_combo = QComboBox()
        self.mode_combo.addItem("Side by Side", DualImageMode.SIDE_BY_SIDE)
        self.mode_combo.addItem("Overlay", DualImageMode.OVERLAY)
        self.mode_combo.addItem("Blink", DualImageMode.BLINK)
        self.mode_combo.currentIndexChanged.connect(self._on_mode_changed)
        layout.addWidget(self.mode_combo)

        return widget

    def _create_overlay_controls(self) -> QWidget:
        """Create overlay opacity controls"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)

        # Opacity label
        self.opacity_label = QLabel("Opacity: 50%")
        layout.addWidget(self.opacity_label)

        # Opacity slider
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setMinimum(0)
        self.opacity_slider.setMaximum(100)
        self.opacity_slider.setValue(50)
        self.opacity_slider.setToolTip("Adjust overlay transparency")
        self.opacity_slider.valueChanged.connect(self._on_opacity_changed)
        layout.addWidget(self.opacity_slider)

        return widget

    def _create_blink_controls(self) -> QWidget:
        """Create blink controls"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)

        # Blink toggle
        self.blink_button = QPushButton("Start Blink")
        self.blink_button.setCheckable(True)
        self.blink_button.setToolTip("Toggle blinking between images")
        self.blink_button.clicked.connect(self._toggle_blink)
        layout.addWidget(self.blink_button)

        # Blink interval
        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("Interval (ms):"))
        self.blink_interval_spin = QSpinBox()
        self.blink_interval_spin.setMinimum(100)
        self.blink_interval_spin.setMaximum(5000)
        self.blink_interval_spin.setValue(1000)
        self.blink_interval_spin.setToolTip("Blink interval in milliseconds")
        self.blink_interval_spin.valueChanged.connect(self._on_blink_interval_changed)
        interval_layout.addWidget(self.blink_interval_spin)
        layout.addLayout(interval_layout)

        return widget

    def _create_sync_controls(self) -> QWidget:
        """Create synchronization controls"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)

        # Sync navigation
        self.sync_navigation_cb = QCheckBox("Sync Navigation")
        self.sync_navigation_cb.setChecked(True)
        self.sync_navigation_cb.setToolTip("Synchronize pan and zoom between images")
        self.sync_navigation_cb.toggled.connect(self._on_sync_navigation_toggled)
        layout.addWidget(self.sync_navigation_cb)

        # Sync ROIs
        self.sync_rois_cb = QCheckBox("Sync ROIs")
        self.sync_rois_cb.setChecked(True)
        self.sync_rois_cb.setToolTip("Share ROIs between linked images")
        self.sync_rois_cb.toggled.connect(self._on_sync_rois_toggled)
        layout.addWidget(self.sync_rois_cb)

        return widget

    def _create_view_container(self, title: str) -> QGroupBox:
        """Create a container for an image view"""
        container = QGroupBox(title)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(2, 2, 2, 2)

        # Placeholder label
        placeholder = QLabel("No image selected")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet("color: gray; font-style: italic;")
        layout.addWidget(placeholder)

        return container

    def set_primary_image(self, image_index: int) -> bool:
        """Set the primary image for dual view"""
        if not self._validate_image_index(image_index):
            return False

        self._primary_index = image_index

        # Create or get raster view
        raster_view = self._get_or_create_raster_view(image_index)
        if not raster_view:
            return False

        # Update container to actually show the raster view
        self._update_view_container(
            self.primary_view_container,
            raster_view,
            f"Primary Image ({self._get_image_name(image_index)})",
        )

        # Update link state if both images are set
        self._check_auto_link()

        self.primary_image_changed.emit(image_index)
        logger.debug(f"Set primary image to index {image_index}")
        return True

    def set_secondary_image(self, image_index: int) -> bool:
        """Set the secondary image for dual view"""
        if not self._validate_image_index(image_index):
            return False

        if image_index == self._primary_index:
            logger.warning("Secondary image cannot be the same as primary image")
            return False

        self._secondary_index = image_index

        # Create or get raster view
        raster_view = self._get_or_create_raster_view(image_index)
        if not raster_view:
            return False

        # Update container to actually show the raster view
        self._update_view_container(
            self.secondary_view_container,
            raster_view,
            f"Secondary Image ({self._get_image_name(image_index)})",
        )

        # Update link state if both images are set
        self._check_auto_link()

        self.secondary_image_changed.emit(image_index)
        logger.debug(f"Set secondary image to index {image_index}")
        return True

    def get_primary_index(self) -> Optional[int]:
        """Get the primary image index"""
        return self._primary_index

    def get_secondary_index(self) -> Optional[int]:
        """Get the secondary image index"""
        return self._secondary_index

    def clear_images(self):
        """Clear both images from the dual view"""
        if self._is_linked:
            self._toggle_link()  # Unlink first

        self._primary_index = None
        self._secondary_index = None

        # Clear containers
        self._clear_view_container(self.primary_view_container, "Primary Image")
        self._clear_view_container(self.secondary_view_container, "Secondary Image")

        self._update_control_states()

    # Private methods
    def _connect_signals(self):
        """Connect controller signals"""
        self.controller.mode_changed.connect(self._on_controller_mode_changed)
        self.controller.overlay_opacity_changed.connect(
            self._on_controller_opacity_changed
        )
        self.controller.blink_state_changed.connect(self._on_controller_blink_changed)
        self.controller.dual_view_activated.connect(self._on_dual_view_activated)
        self.controller.dual_view_deactivated.connect(self._on_dual_view_deactivated)
        self.controller.view_sync_requested.connect(self._on_view_sync_requested)

    def _toggle_link(self):
        """Toggle link state between images"""
        if not self._can_link():
            logger.debug("Cannot link - conditions not met")
            return

        if self._is_linked:
            # Unlink
            logger.debug("Unlinking images")
            success = self.controller.deactivate_dual_view()
            if success:
                self._is_linked = False
                self.link_button.setText("Link Images")
                self.link_button.setChecked(False)
                self.link_toggled.emit(False)
        else:
            # Link
            logger.debug(
                f"Linking images: {self._primary_index} and {self._secondary_index}"
            )
            config = self._get_current_config()
            logger.debug(f"Link config: sync_navigation={config.sync_navigation}")

            success = self.controller.activate_dual_view(
                self._primary_index, self._secondary_index, config
            )
            if success:
                self._is_linked = True
                self.link_button.setText("Unlink Images")
                self.link_button.setChecked(True)
                self.link_toggled.emit(True)

                # Force setup navigation sync
                logger.debug("Setting up navigation sync after linking")
                self._setup_navigation_sync()

                # DEBUG: Check the complete state after linking
                self.debug_dual_view_state()

            else:
                logger.error("Failed to activate dual view")

        self._update_control_states()

    def _can_link(self) -> bool:
        """Check if images can be linked"""
        return (
            self._primary_index is not None
            and self._secondary_index is not None
            and self._primary_index != self._secondary_index
        )

    def _check_auto_link(self):
        """Check if we should auto-link when both images are set"""
        if self._can_link() and not self._is_linked:
            # Enable link button
            self.link_button.setEnabled(True)

    def _get_current_config(self) -> DualImageConfig:
        """Build current configuration from UI state"""
        config = DualImageConfig()

        # Get mode from combo box
        mode_data = self.mode_combo.currentData()
        if mode_data:
            config.mode = mode_data

        # Get other settings
        config.overlay_opacity = self.opacity_slider.value() / 100.0
        config.blink_interval = self.blink_interval_spin.value()
        config.blink_enabled = self.blink_button.isChecked()
        config.sync_navigation = self.sync_navigation_cb.isChecked()
        config.sync_rois = self.sync_rois_cb.isChecked()
        config.link_type = LinkType.PIXEL_BASED  # Default for now

        return config

    def _update_control_states(self):
        """Update the enabled/disabled state of controls"""
        can_link = self._can_link()
        is_linked = self._is_linked

        # Link button
        self.link_button.setEnabled(can_link)

        # Mode and other controls
        self.mode_combo.setEnabled(is_linked)
        self.opacity_slider.setEnabled(is_linked)
        self.blink_button.setEnabled(is_linked)
        self.blink_interval_spin.setEnabled(is_linked)
        self.sync_navigation_cb.setEnabled(is_linked)
        self.sync_rois_cb.setEnabled(is_linked)

    def _get_or_create_raster_view(self, image_index: int) -> Optional[RasterView]:
        """Get existing or create new raster view for image"""
        if image_index in self._raster_views:
            return self._raster_views[image_index]

        try:
            # Import here to avoid circular imports
            from varda.features.image_view_raster.raster_viewmodel import (
                RasterViewModel,
            )

            # Create view model and view
            view_model = RasterViewModel(self.proj, image_index)
            raster_view = RasterView(view_model, self)

            # Store the view
            self._raster_views[image_index] = raster_view

            # Connect navigation signals immediately
            self._connect_view_signals(raster_view, image_index)

            return raster_view

        except Exception as e:
            logger.error(f"Failed to create raster view for image {image_index}: {e}")
            return None

    def _connect_view_signals(self, raster_view: RasterView, image_index: int):
        """Connect signals for a raster view"""
        try:
            # Disconnect first to avoid duplicate connections
            try:
                raster_view.sigNavigationChanged.disconnect()
            except:
                pass

            try:
                raster_view.sigROIChanged.disconnect()
            except:
                pass

            # Connect navigation change signal
            if hasattr(raster_view, "sigNavigationChanged"):
                raster_view.sigNavigationChanged.connect(
                    lambda state, idx=image_index: self._on_navigation_changed(
                        idx, state
                    )
                )
                logger.debug(f"Connected navigation signal for image {image_index}")

            # Connect ROI change signal
            if hasattr(raster_view, "sigROIChanged"):
                raster_view.sigROIChanged.connect(
                    lambda roi_id, idx=image_index: self._on_roi_changed(idx, roi_id)
                )
                logger.debug(f"Connected ROI signal for image {image_index}")

        except Exception as e:
            logger.error(
                f"Failed to connect signals for raster view {image_index}: {e}"
            )

    def _update_view_container(self, container: QGroupBox, view: QWidget, title: str):
        """Update a view container with a new view"""
        # Clear existing layout
        layout = container.layout()
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().setParent(None)

        # Add new view
        container.setTitle(title)
        layout.addWidget(view)

        # Ensure view is visible and properly sized
        view.setVisible(True)
        view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        logger.debug(f"Updated view container: {title}")

    def _clear_view_container(self, container: QGroupBox, title: str):
        """Clear a view container"""
        # Clear existing layout
        layout = container.layout()
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().setParent(None)

        # Add placeholder
        placeholder = QLabel("No image selected")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet("color: gray; font-style: italic;")
        container.setTitle(title)
        layout.addWidget(placeholder)

    def _validate_image_index(self, index: int) -> bool:
        """Validate that an image index is valid"""
        try:
            images = self.proj.getAllImages()
            return 0 <= index < len(images)
        except Exception:
            return False

    def _get_image_name(self, index: int) -> str:
        """Get a display name for an image"""
        try:
            image = self.proj.getImage(index)
            if hasattr(image.metadata, "name") and image.metadata.name:
                return image.metadata.name
            elif hasattr(image.metadata, "filePath") and image.metadata.filePath:
                import os

                return os.path.basename(image.metadata.filePath)
            else:
                return f"Image {index}"
        except Exception:
            return f"Image {index}"

    # Event handlers

    def _on_mode_changed(self):
        """Handle display mode change"""
        if self._is_linked:
            mode = self.mode_combo.currentData()
            if mode:
                self.controller.set_display_mode(mode)

    def _on_opacity_changed(self, value):
        """Handle opacity slider change"""
        opacity = value / 100.0
        self.opacity_label.setText(f"Opacity: {value}%")
        if self._is_linked:
            self.controller.set_overlay_opacity(opacity)

    def _toggle_blink(self):
        """Handle blink button toggle"""
        if self._is_linked:
            is_blinking = self.controller.toggle_blink()

            # Update button text and state
            if is_blinking:
                self.blink_button.setText("Stop Blink")
                self.blink_button.setChecked(True)
            else:
                self.blink_button.setText("Start Blink")
                self.blink_button.setChecked(False)

    def _on_blink_interval_changed(self, value):
        """Handle blink interval change"""
        if self._is_linked:
            self.controller.set_blink_interval(value)

    def _on_sync_navigation_toggled(self, checked):
        """Handle sync navigation toggle"""
        if self._is_linked and self.controller.get_current_config():
            config = self.controller.get_current_config()
            config.sync_navigation = checked
            if self._primary_index is not None and self._secondary_index is not None:
                self.controller.link_manager.update_link_config(
                    self._primary_index, self._secondary_index, config
                )

    def _on_sync_rois_toggled(self, checked):
        """Handle sync ROIs toggle"""
        if self._is_linked and self.controller.get_current_config():
            config = self.controller.get_current_config()
            config.sync_rois = checked
            if self._primary_index is not None and self._secondary_index is not None:
                self.controller.link_manager.update_link_config(
                    self._primary_index, self._secondary_index, config
                )

    # Controller event handlers

    def _on_controller_mode_changed(self, mode):
        """Handle mode change from controller"""
        # Update UI to reflect controller state
        for i in range(self.mode_combo.count()):
            if self.mode_combo.itemData(i) == mode:
                self.mode_combo.setCurrentIndex(i)
                break

    def _on_controller_opacity_changed(self, opacity):
        """Handle opacity change from controller"""
        value = int(opacity * 100)
        self.opacity_slider.setValue(value)
        self.opacity_label.setText(f"Opacity: {value}%")

    def _on_controller_blink_changed(self, enabled):
        """Handle blink state change from controller"""
        self.blink_button.setChecked(enabled)
        self.blink_button.setText("Stop Blink" if enabled else "Start Blink")

        # Update UI state based on blink mode
        if enabled:
            # In blink mode, disable overlay controls
            self.opacity_slider.setEnabled(False)
        else:
            # Re-enable overlay controls when not blinking
            mode = self.mode_combo.currentData()
            self.opacity_slider.setEnabled(mode == DualImageMode.OVERLAY)

    def _on_dual_view_activated(self, primary_index, secondary_index):
        """Handle dual view activation"""
        logger.debug(f"Dual view activated: {primary_index} <-> {secondary_index}")

        # Set up navigation synchronization with a slight delay to ensure views are ready
        QTimer.singleShot(100, self._setup_navigation_sync)

    def _on_dual_view_deactivated(self):
        """Handle dual view deactivation"""
        logger.debug("Dual view deactivated")

    # sync navigation methods
    def _connect_signals(self):
        """Connect controller signals"""
        self.controller.mode_changed.connect(self._on_controller_mode_changed)
        self.controller.overlay_opacity_changed.connect(
            self._on_controller_opacity_changed
        )
        self.controller.blink_state_changed.connect(self._on_controller_blink_changed)
        self.controller.dual_view_activated.connect(self._on_dual_view_activated)
        self.controller.dual_view_deactivated.connect(self._on_dual_view_deactivated)
        self.controller.view_sync_requested.connect(self._on_view_sync_requested)

    def _on_dual_view_activated(self, primary_index, secondary_index):
        """Handle dual view activation"""
        logger.debug(f"Dual view activated: {primary_index} <-> {secondary_index}")

        # Ensure we have the views
        primary_view = self._raster_views.get(primary_index)
        secondary_view = self._raster_views.get(secondary_index)

        if primary_view and secondary_view:
            # Set up navigation synchronization immediately
            self._setup_navigation_sync()
            logger.debug("Views found and sync setup initiated")
        else:
            logger.error(
                f"Views missing during activation: primary={primary_view is not None}, secondary={secondary_view is not None}"
            )

    def _setup_navigation_sync(self):
        """Set up navigation synchronization between the two views"""
        if self._primary_index is None or self._secondary_index is None:
            logger.warning("Cannot setup navigation sync - missing image indices")
            return

        # Get the raster views
        primary_view = self._raster_views.get(self._primary_index)
        secondary_view = self._raster_views.get(self._secondary_index)

        if not primary_view or not secondary_view:
            logger.error(
                f"Cannot setup navigation sync - missing views: primary={primary_view is not None}, secondary={secondary_view is not None}"
            )
            return

        logger.debug(
            f"Setting up navigation sync between views for images {self._primary_index} and {self._secondary_index}"
        )

        # Set both views to dual mode
        primary_view.set_dual_mode(True, False)  # Primary view
        secondary_view.set_dual_mode(True, True)  # Secondary view (overlay)

        # Ensure signals are connected
        self._connect_view_signals(primary_view, self._primary_index)
        self._connect_view_signals(secondary_view, self._secondary_index)

        # Update view references in controller
        self.controller.set_view_references(primary_view, secondary_view)

        logger.debug("Navigation synchronization set up successfully")

    def _on_navigation_changed(self, source_index: int, view_state: dict):
        """Handle navigation changes from one of the views"""
        if self._is_linked and self.controller:
            logger.debug(
                f"Navigation changed in image {source_index}, syncing to other view"
            )
            self.controller.sync_navigation(source_index, view_state)

    def _on_roi_changed(self, source_index: int, roi_id: str):
        """Handle ROI changes from one of the views"""
        if self._is_linked and self.controller:
            self.controller.sync_roi(source_index, roi_id)

    def _on_view_sync_requested(self, target_index: int, sync_data: dict):
        """Handle view synchronization requests from controller"""
        logger.debug(f"=== SYNC REQUESTED TO INDEX {target_index} ===")

        # Debug the current state before applying sync
        self.debug_dual_view_state()

        target_view = self._raster_views.get(target_index)
        if target_view:
            logger.debug(f"Found target view for index {target_index}")
            logger.debug(f"Target view visible: {target_view.isVisible()}")
            logger.debug(f"Target view enabled: {target_view.isEnabled()}")

            # Get current range before sync
            if hasattr(target_view, "mainView") and target_view.mainView:
                before_range = target_view.mainView.viewRange()
                logger.debug(f"BEFORE sync - Target view range: {before_range}")

            # Apply the sync
            target_view.sync_navigation_from_other(sync_data)

            # Get range after sync
            if hasattr(target_view, "mainView") and target_view.mainView:
                after_range = target_view.mainView.viewRange()
                logger.debug(f"AFTER sync - Target view range: {after_range}")

                # Check if the range actually changed
                if before_range != after_range:
                    logger.debug("SUCCESS: View range changed after sync")
                else:
                    logger.error("PROBLEM: View range did NOT change after sync")

        else:
            logger.error(f"Target view not found for sync: {target_index}")
            logger.debug(f"Available views: {list(self._raster_views.keys())}")

    def _on_dual_view_deactivated(self):
        """Handle dual view deactivation"""
        logger.debug("Dual view deactivated")

        # Reset views to normal mode
        if self._primary_index in self._raster_views:
            self._raster_views[self._primary_index].set_dual_mode(False)
        if self._secondary_index in self._raster_views:
            self._raster_views[self._secondary_index].set_dual_mode(False)

    def _update_view_container(self, container: QGroupBox, view: QWidget, title: str):
        """Update a view container with a new view"""
        # Clear existing layout
        layout = container.layout()
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().setParent(None)

        # Add new view
        container.setTitle(title)
        layout.addWidget(view)

        # Ensure view is visible and properly sized
        view.setVisible(True)
        view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Force container and view to update
        container.setVisible(True)
        container.update()
        view.update()

        # Ensure the view can receive mouse events for interaction
        view.setEnabled(True)
        view.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, True)

        # CRITICAL: Force the parent widgets to be visible too
        parent = container.parent()
        while parent and parent != self:
            parent.setVisible(True)
            parent.update()
            parent = parent.parent()

        # Force the main dual view widget to be visible
        self.setVisible(True)
        self.update()

        # Process events to ensure visibility changes take effect
        from PyQt6.QtCore import QCoreApplication

        QCoreApplication.processEvents()

        # If this is part of an active link, set up sync
        if self._is_linked:
            self._setup_navigation_sync()

        logger.debug(
            f"Updated view container: {title}, view visible: {view.isVisible()}, container visible: {container.isVisible()}"
        )

    def debug_dual_view_state(self):
        """Debug the complete dual view state"""
        logger.debug("=== DUAL VIEW DEBUG STATE ===")
        logger.debug(f"Primary index: {self._primary_index}")
        logger.debug(f"Secondary index: {self._secondary_index}")
        logger.debug(f"Is linked: {self._is_linked}")

        # Check containers
        logger.debug(
            f"Primary container visible: {self.primary_view_container.isVisible()}"
        )
        logger.debug(
            f"Secondary container visible: {self.secondary_view_container.isVisible()}"
        )
        logger.debug(f"Splitter visible: {self.splitter.isVisible()}")
        logger.debug(f"Splitter sizes: {self.splitter.sizes()}")

        # Check views
        if self._primary_index in self._raster_views:
            primary_view = self._raster_views[self._primary_index]
            logger.debug(f"Primary view exists: {primary_view is not None}")
            logger.debug(f"Primary view visible: {primary_view.isVisible()}")
            logger.debug(f"Primary view parent: {primary_view.parent()}")
            logger.debug(f"Primary view size: {primary_view.size()}")
            if hasattr(primary_view, "mainView") and primary_view.mainView:
                logger.debug(
                    f"Primary mainView range: {primary_view.mainView.viewRange()}"
                )

        if self._secondary_index in self._raster_views:
            secondary_view = self._raster_views[self._secondary_index]
            logger.debug(f"Secondary view exists: {secondary_view is not None}")
            logger.debug(f"Secondary view visible: {secondary_view.isVisible()}")
            logger.debug(f"Secondary view parent: {secondary_view.parent()}")
            logger.debug(f"Secondary view size: {secondary_view.size()}")
            if hasattr(secondary_view, "mainView") and secondary_view.mainView:
                logger.debug(
                    f"Secondary mainView range: {secondary_view.mainView.viewRange()}"
                )

        logger.debug("===============================")
