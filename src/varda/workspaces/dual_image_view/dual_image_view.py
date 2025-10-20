"""
Dual Image View Widget

Main widget for displaying two images side-by-side with dual view controls
and synchronization capabilities.
"""

import logging
from typing import Optional, Dict
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
    QSizePolicy,
)

from .dual_image_types import DualImageMode, LinkType, DualImageConfig
from .dual_image_view_controller import DualImageViewController
from .dual_image_tool_manager import DualImageToolManager
from .spectral_plot_tool import SpectralPlotTool
from varda._old.image_view_raster.raster_view import RasterView
from varda.project import ProjectContext

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

        # Initialize tool manager
        self.tool_manager = DualImageToolManager(project_context, self)
        self._setup_tools()

        # State tracking
        self._primary_index: Optional[int] = None
        self._secondary_index: Optional[int] = None
        self._raster_views: Dict[int, RasterView] = {}  # image_index -> RasterView
        self._is_linked = False
        self._current_active_tool: Optional[str] = None

        # UI components
        self.primary_view_container = None
        self.secondary_view_container = None
        self.control_panel = None
        self.splitter = None
        self.tool_panel_splitter = None  # Splitter for tool panel

        # Control widgets
        self.mode_combo = None
        self.opacity_slider = None
        self.opacity_label = None
        self.blink_button = None
        self.blink_interval_spin = None
        self.link_button = None
        self.sync_navigation_cb = None
        self.sync_rois_cb = None
        self.spectral_tool_button = None
        self.tool_buttons = {}
        self._tool_controls_layout = None
        self.future_tools_label = None

        # Initialize UI
        self._init_ui()
        self._connect_signals()

        logger.debug("DualImageView initialized with tool manager")

    def _init_ui(self):
        """Initialize the user interface"""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        # Control panel
        self.control_panel = self._create_control_panel()
        main_layout.addWidget(self.control_panel)

        # Main content splitter (horizontal: images | viewport_tools)
        self.tool_panel_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.tool_panel_splitter.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        # Image view splitter (left side of main splitter)
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

        # Set equal split for images
        self.splitter.setSizes([400, 400])

        # Add image splitter to main splitter
        self.tool_panel_splitter.addWidget(self.splitter)

        # Add tool panel to main splitter (right side) - ALWAYS VISIBLE
        tool_panel = self.tool_manager.get_tool_panel_widget()

        tool_panel.setMaximumWidth(350)
        tool_panel.setMinimumWidth(280)
        self.tool_panel_splitter.addWidget(tool_panel)

        # Set proportional split: 75% images, 25% viewport_tools
        self.tool_panel_splitter.setSizes([750, 250])

        main_layout.addWidget(self.tool_panel_splitter)

        # Initially disable controls
        self._update_control_states()

    def _setup_tools(self):
        """Register available viewport_tools with the tool manager"""
        # Register spectral plot tool
        self.tool_manager.register_tool(SpectralPlotTool, "spectral_plot")

        # Connect tool manager signals
        self.tool_manager.tool_activated.connect(self._on_tool_activated)
        self.tool_manager.tool_deactivated.connect(self._on_tool_deactivated)
        self.tool_manager.click_handled.connect(self._on_tool_click_handled)

    def _create_tool_controls(self) -> QWidget:
        """Create tool activation controls - redesigned as tool switcher"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)

        # STORE LAYOUT REFERENCE for adding future viewport_tools
        self._tool_controls_layout = layout

        # Tool switcher buttons
        self.spectral_tool_button = QPushButton("Spectral")
        self.spectral_tool_button.setCheckable(True)
        self.spectral_tool_button.setToolTip("Spectral plotting tool")
        self.spectral_tool_button.clicked.connect(
            lambda: self._switch_to_tool("spectral_plot")
        )
        layout.addWidget(self.spectral_tool_button)

        # Store for future reference
        self.tool_buttons["spectral_plot"] = self.spectral_tool_button

        # Placeholder for future viewport_tools - store reference to this too
        self.future_tools_label = QLabel("More viewport_tools coming...")
        self.future_tools_label.setStyleSheet(
            "color: gray; font-style: italic; font-size: 10px;"
        )
        layout.addWidget(self.future_tools_label)

        return widget

    def _switch_to_tool(self, tool_name: str):
        """Switch active tool in the tool canvas"""
        logger.debug(f"Switching to tool: {tool_name}")

        # Deactivate current tool if different
        if self._current_active_tool and self._current_active_tool != tool_name:
            self.tool_manager.deactivate_tool(self._current_active_tool)
            # Update button state for old tool
            if self._current_active_tool in self.tool_buttons:
                self.tool_buttons[self._current_active_tool].setChecked(False)

        # Activate new tool
        if tool_name != self._current_active_tool:
            if self.tool_manager.activate_tool(tool_name):
                self._current_active_tool = tool_name
                # Update button state for new tool
                if tool_name in self.tool_buttons:
                    self.tool_buttons[tool_name].setChecked(True)
                logger.info(f"Switched to tool: {tool_name}")
            else:
                logger.error(f"Failed to switch to tool: {tool_name}")
                # Reset button if activation failed
                if tool_name in self.tool_buttons:
                    self.tool_buttons[tool_name].setChecked(False)

    def _create_control_panel(self) -> QGroupBox:
        # from PyQt6.QtWidgets import QFrame
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

        # Separator
        separator5 = QFrame()
        separator5.setFrameShape(QFrame.Shape.VLine)
        separator5.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator5)

        # Tool controls
        tool_group = self._create_tool_controls()
        layout.addWidget(tool_group)

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
        self.link_button.setToolTip("Link/unlink the two images for synchronized viewing")
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

        # Force stretch update after setting the image
        self._force_stretch_update(raster_view, image_index)

        # Update link state and activate default tool if both images are set
        self._check_auto_link()

        # Update tool manager with new image indices
        if self._secondary_index is not None:
            self.tool_manager.set_image_indices(
                self._primary_index, self._secondary_index
            )

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

        # Force stretch update after setting the image
        self._force_stretch_update(raster_view, image_index)

        # Update link state and activate default tool if both images are set
        self._check_auto_link()

        # Update tool manager with new image indices
        if self._primary_index is not None:
            self.tool_manager.set_image_indices(
                self._primary_index, self._secondary_index
            )

        self.secondary_image_changed.emit(image_index)
        logger.debug(f"Set secondary image to index {image_index}")
        return True

    def _force_stretch_update(self, raster_view, image_index: int):
        """Force the raster view to update with current stretch values"""
        try:
            logger.debug(f"=== FORCING STRETCH UPDATE FOR IMAGE {image_index} ===")

            # Get the current stretch from the project
            image = self.proj.getImage(image_index)

            # Try to get the stretch index from the main view's RasterView
            main_stretch_index = self._get_main_view_stretch_index(image_index)
            if main_stretch_index is not None:
                stretch_index = main_stretch_index
                logger.debug(f"Using main view stretch index: {stretch_index}")
            else:
                stretch_index = raster_view.viewModel.stretchIndex
                logger.debug(f"Using dual view stretch index: {stretch_index}")

            # Update the dual view's stretch index to match
            raster_view.viewModel.stretchIndex = stretch_index

            logger.debug(
                f"Image has {len(image.stretch)} stretches, using index {stretch_index}"
            )

            current_stretch = image.stretch[stretch_index]
            stretch_levels = current_stretch.toList()

            logger.debug(
                f"Current stretch levels for image {image_index}: {stretch_levels}"
            )
            logger.debug(f"Stretch levels type: {type(stretch_levels[0][0])}")

            # Get current raster data
            raster_data = raster_view.viewModel.getRasterFromBand()
            logger.debug(f"Raster data shape: {raster_data.shape}")
            logger.debug(f"Raster data range: {raster_data.min()} to {raster_data.max()}")

            # Update the cache in the raster view
            raster_view.current_stretch_levels = stretch_levels
            logger.debug(f"Updated raster_view.current_stretch_levels")

            # Apply the stretch to all image components
            if hasattr(raster_view, "contextImage") and raster_view.contextImage:
                logger.debug("Updating contextImage with stretch levels")
                raster_view.contextImage.setImage(raster_data, levels=stretch_levels)

            if hasattr(raster_view, "mainImage") and raster_view.mainImage:
                logger.debug("Updating mainImage with stretch levels")
                raster_view.mainImage.setLevels(stretch_levels)

            if hasattr(raster_view, "zoomImage") and raster_view.zoomImage:
                logger.debug("Updating zoomImage with stretch levels")
                raster_view.zoomImage.setLevels(stretch_levels)

            # Force view updates
            if hasattr(raster_view, "contextView") and raster_view.contextView:
                raster_view.contextView.update()
                logger.debug("Updated contextView")

            if hasattr(raster_view, "mainView") and raster_view.mainView:
                raster_view.mainView.update()
                logger.debug("Updated mainView")

            if hasattr(raster_view, "zoomView") and raster_view.zoomView:
                raster_view.zoomView.update()
                logger.debug("Updated zoomView")

            # Also try updating the raster view itself
            raster_view.update()
            raster_view.repaint()
            logger.debug("Updated raster_view widget")

            logger.debug(
                f"=== COMPLETED FORCED STRETCH UPDATE FOR IMAGE {image_index} ==="
            )

        except Exception as e:
            logger.error(f"Error forcing stretch update for image {image_index}: {e}")
            import traceback

            logger.error(traceback.format_exc())

    def _get_main_view_stretch_index(self, image_index: int) -> Optional[int]:
        """Try to get the stretch index from the main view's RasterView"""
        try:
            # Walk up the parent hierarchy to find MainGUI
            parent = self.parent()
            while parent:
                if hasattr(parent, "rasterViews") and hasattr(parent, "proj"):
                    # Found MainGUI
                    main_gui = parent
                    if image_index in main_gui.rasterViews:
                        main_raster_view = main_gui.rasterViews[image_index]
                        if hasattr(main_raster_view, "viewModel") and hasattr(
                            main_raster_view.viewModel, "stretchIndex"
                        ):
                            stretch_index = main_raster_view.viewModel.stretchIndex
                            # REMOVE this debug line: logger.debug(f"Found main view stretch index {stretch_index} for image {image_index}")
                            return stretch_index
                    break
                parent = parent.parent()

            # Also try to get MainGUI through the project context if it has a reference
            if hasattr(self.proj, "main_window"):
                main_gui = self.proj.main_window
                if (
                    hasattr(main_gui, "rasterViews")
                    and image_index in main_gui.rasterViews
                ):
                    main_raster_view = main_gui.rasterViews[image_index]
                    if hasattr(main_raster_view, "viewModel") and hasattr(
                        main_raster_view.viewModel, "stretchIndex"
                    ):
                        stretch_index = main_raster_view.viewModel.stretchIndex
                        # REMOVE this debug line: logger.debug(f"Found main view stretch index {stretch_index} for image {image_index} via project")
                        return stretch_index

        except Exception as e:
            logger.error(
                f"Error getting main view stretch index for image {image_index}: {e}"
            )

        return None

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
        """Check if both images are set and activate default tool"""
        if self._primary_index is not None and self._secondary_index is not None:
            # Both images are set, activate default tool if none is active
            if not self._current_active_tool:
                self._switch_to_tool("spectral_plot")

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

            # Connect directly to project context signals for this image
            self._connect_project_signals(image_index)

            return raster_view

        except Exception as e:
            logger.error(f"Failed to create raster view for image {image_index}: {e}")
            return None

    def _connect_project_signals(self, image_index: int):
        """Connect to project context signals for an image"""
        try:
            # Connect to BOTH versions of the project data change signals
            # Version 1: 2-parameter signal (used by RasterViewModel)
            self.proj.sigDataChanged[int, ProjectContext.ChangeType].connect(
                lambda idx, change_type, idx_to_monitor=image_index: self._on_project_data_changed(
                    idx, change_type, idx_to_monitor
                )
            )

            # Version 2: 3-parameter signal (used by HistogramViewModel and others)
            self.proj.sigDataChanged[
                int, ProjectContext.ChangeType, ProjectContext.ChangeModifier
            ].connect(
                lambda idx, change_type, change_modifier, idx_to_monitor=image_index: self._on_project_data_changed_3param(
                    idx, change_type, change_modifier, idx_to_monitor
                )
            )

            logger.debug(f"Connected to both signal versions for image {image_index}")
        except Exception as e:
            logger.error(
                f"Failed to connect project signals for image {image_index}: {e}"
            )

    def _on_project_data_changed_3param(
        self, changed_index: int, change_type, change_modifier, monitored_index: int
    ):
        """Handle 3-parameter project data changes for monitored images"""
        # Only process UPDATE changes (not ADD/REMOVE)
        from varda.project import ProjectContext

        if change_modifier != ProjectContext.ChangeModifier.UPDATE:
            return

        # Delegate to the main handler
        self._on_project_data_changed(changed_index, change_type, monitored_index)

    def _on_project_data_changed(
        self, changed_index: int, change_type, monitored_index: int
    ):
        """Handle project data changes for monitored images"""
        # Only process changes for the images we're monitoring
        if changed_index != monitored_index:
            return

        try:
            from varda.project import ProjectContext

            logger.debug(
                f"=== DUAL VIEW: Project data changed for image {changed_index}, type: {change_type} ==="
            )

            # Get the raster view for this image
            raster_view = self._raster_views.get(changed_index)
            if not raster_view:
                logger.error(f"No raster view found for image {changed_index}")
                return

            logger.debug(f"Found raster view for image {changed_index}")

            if change_type == ProjectContext.ChangeType.STRETCH:
                logger.debug(f"Processing stretch change for image {changed_index}")
                self._refresh_image_display(raster_view, changed_index, "stretch")

            elif change_type == ProjectContext.ChangeType.BAND:
                logger.debug(f"Processing band change for image {changed_index}")
                self._refresh_image_display(raster_view, changed_index, "band")

        except Exception as e:
            logger.error(
                f"Error handling project data change for image {changed_index}: {e}"
            )
            import traceback

            logger.error(traceback.format_exc())

    def _refresh_image_display(self, raster_view, image_index: int, change_type: str):
        """Force a complete refresh of the image display"""
        try:
            logger.debug(
                f"=== REFRESHING DISPLAY FOR IMAGE {image_index} ({change_type}) ==="
            )

            if not hasattr(raster_view, "viewModel") or not raster_view.viewModel:
                logger.error(f"RasterView for image {image_index} has no viewModel")
                return

            # Log the current stretch values
            current_stretch = raster_view.viewModel.getSelectedStretch()
            stretch_levels = current_stretch.toList()
            logger.debug(f"Current stretch levels: {stretch_levels}")

            # Get fresh raster data
            raster_data = raster_view.viewModel.getRasterFromBand()
            logger.debug(f"Raster data shape: {raster_data.shape}")

            # Method 1: Try calling the existing change handlers
            logger.debug("Method 1: Calling existing change handlers")
            if change_type == "stretch":
                raster_view._onStretchChanged()
            elif change_type == "band":
                raster_view._onBandChanged()

            # Method 2: Force complete view refresh similar to _updateViews
            logger.debug("Method 2: Force complete view refresh")
            try:
                raster_view._updateViews()
            except Exception as e:
                logger.error(f"Error calling _updateViews: {e}")

            # Method 3: Direct image item updates
            logger.debug("Method 3: Direct image item updates")
            if hasattr(raster_view, "contextImage") and raster_view.contextImage:
                logger.debug("Updating contextImage")
                raster_view.contextImage.setImage(raster_data, levels=stretch_levels)

            # Method 4: Force widget updates at multiple levels
            logger.debug("Method 4: Force widget updates")
            self._force_view_updates(raster_view)

            # Method 5: Update container
            if image_index == self._primary_index:
                logger.debug("Updating primary container")
                self._force_container_update(self.primary_view_container)
            elif image_index == self._secondary_index:
                logger.debug("Updating secondary container")
                self._force_container_update(self.secondary_view_container)

            logger.debug(f"=== COMPLETED REFRESH FOR IMAGE {image_index} ===")

        except Exception as e:
            logger.error(f"Error refreshing display for image {image_index}: {e}")
            import traceback

            logger.error(traceback.format_exc())

    def _force_view_updates(self, raster_view):
        """Force all views within a raster view to update"""
        try:
            # Update individual view widgets
            if hasattr(raster_view, "contextView") and raster_view.contextView:
                raster_view.contextView.update()

            if hasattr(raster_view, "mainView") and raster_view.mainView:
                raster_view.mainView.update()

            if hasattr(raster_view, "zoomView") and raster_view.zoomView:
                raster_view.zoomView.update()

            # Update the raster view itself
            raster_view.update()
            raster_view.repaint()

        except Exception as e:
            logger.error(f"Error forcing view updates: {e}")

    def _force_container_update(self, container):
        """Force a container to update its display"""
        try:
            container.update()
            container.repaint()

            # Also update the child widgets
            for i in range(container.layout().count()):
                widget = container.layout().itemAt(i).widget()
                if widget:
                    widget.update()
                    widget.repaint()

        except Exception as e:
            logger.error(f"Error forcing container update: {e}")

    def _connect_view_signals(self, raster_view: RasterView, image_index: int):
        """Connect signals for a raster view"""
        try:
            logger.debug(f"Connecting signals for raster view {image_index}")

            # Connect to the RasterViewModel signals directly
            if hasattr(raster_view, "viewModel") and raster_view.viewModel:
                vm = raster_view.viewModel

                # Disconnect any existing connections first
                try:
                    vm.sigStretchChanged.disconnect()
                    vm.sigBandChanged.disconnect()
                except:
                    pass

                # Connect stretch change signal with proper slot
                vm.sigStretchChanged.connect(
                    lambda idx=image_index: self._on_viewmodel_stretch_changed(idx)
                )

                # Connect band change signal with proper slot
                vm.sigBandChanged.connect(
                    lambda idx=image_index: self._on_viewmodel_band_changed(idx)
                )

                logger.debug(f"Connected ViewModel signals for image {image_index}")

            # Set up polling to monitor main view stretch index changes
            self._setup_stretch_monitoring(image_index)

            # Also connect navigation and ROI signals
            # if hasattr(raster_view, "sigNavigationChanged"):
            #     try:
            #         raster_view.sigNavigationChanged.disconnect()
            #     except:
            #         pass
            #     raster_view.sigNavigationChanged.connect(
            #         lambda state, idx=image_index: self._on_navigation_changed(idx, state)
            #     )

            # if hasattr(raster_view, "sigROIChanged"):
            #     try:
            #         raster_view.sigROIChanged.disconnect()
            #     except:
            #         pass
            #     raster_view.sigROIChanged.connect(
            #         lambda roi_id, idx=image_index: self._on_roi_changed(idx, roi_id)
            #     )

            if hasattr(raster_view, "sigImageClicked"):
                # Connect for navigation sync
                raster_view.sigImageClicked.connect(
                    lambda x, y, idx=image_index: self._on_view_clicked(idx, x, y)
                )

            if hasattr(raster_view, "sigNavigationChanged"):
                raster_view.sigNavigationChanged.connect(
                    lambda state, idx=image_index: self._on_navigation_changed(idx, state)
                )

            if hasattr(raster_view, "sigROIChanged"):
                raster_view.sigROIChanged.connect(
                    lambda roi_id, idx=image_index: self._on_roi_changed(idx, roi_id)
                )

            if hasattr(raster_view, "sigStretchChanged"):
                raster_view.sigStretchChanged.connect(
                    lambda idx=image_index: self._on_stretch_changed(idx)
                )

            logger.debug(f"Connected signals for raster view {image_index}")

        except Exception as e:
            logger.error(f"Failed to connect signals for raster view {image_index}: {e}")

    def _on_view_clicked(self, image_index: int, x: int, y: int):
        """Handle clicks on either image view"""
        # Determine view type
        view_type = "primary" if image_index == self._primary_index else "secondary"

        # Route to tool manager first
        tool_handled = self.tool_manager.handle_click(image_index, x, y, view_type)

        if not tool_handled:
            # If no tool handled it, continue with normal click handling
            logger.debug(
                f"Click at ({x}, {y}) on {view_type} image not handled by viewport_tools"
            )

    # Methods to handle tool activation/deactivation
    def _on_tool_activated(self, tool_name: str):
        """Handle tool activation"""
        logger.info(f"Tool activated: {tool_name}")
        self._current_active_tool = tool_name

    def _on_tool_deactivated(self, tool_name: str):
        """Handle tool deactivation"""
        logger.info(f"Tool deactivated: {tool_name}")
        if self._current_active_tool == tool_name:
            self._current_active_tool = None

    def _on_tool_click_handled(
        self, tool_name: str, image_index: int, x: int, y: int, view_type: str
    ):
        """Handle notification that a tool processed a click"""
        logger.debug(
            f"Tool '{tool_name}' handled click at ({x}, {y}) on {view_type} image"
        )

    def add_tool_button(self, tool_name: str, display_name: str, tooltip: str = ""):
        """Add a new tool button to the control panel"""
        if hasattr(self, "_tool_controls_layout") and self._tool_controls_layout:
            button = QPushButton(display_name)
            button.setCheckable(True)
            button.setToolTip(tooltip)
            button.clicked.connect(lambda: self._switch_to_tool(tool_name))

            # Insert before the "More viewport_tools coming..." label
            # Find the position of the label
            label_index = -1
            for i in range(self._tool_controls_layout.count()):
                item = self._tool_controls_layout.itemAt(i)
                if item and item.widget() == self.future_tools_label:
                    label_index = i
                    break

            if label_index >= 0:
                self._tool_controls_layout.insertWidget(label_index, button)
            else:
                # Fallback: add at the end
                self._tool_controls_layout.addWidget(button)

            self.tool_buttons[tool_name] = button
            logger.debug(f"Added tool button: {tool_name}")
        else:
            logger.error("Tool controls layout not available for adding button")

    def _setup_stretch_monitoring(self, image_index: int):
        """Set up monitoring for stretch index changes in the main view"""
        try:
            if not hasattr(self, "_stretch_monitors"):
                self._stretch_monitors = {}

            # Create a timer to periodically check the main view's stretch index
            from PyQt6.QtCore import QTimer

            timer = QTimer(self)
            timer.timeout.connect(
                lambda idx=image_index: self._check_stretch_index_change(idx)
            )
            timer.start(500)  # Check every 500ms

            self._stretch_monitors[image_index] = {
                "timer": timer,
                "last_stretch_index": None,
            }

            logger.debug(f"Set up stretch monitoring for image {image_index}")

        except Exception as e:
            logger.error(
                f"Failed to set up stretch monitoring for image {image_index}: {e}"
            )

    def _check_stretch_index_change(self, image_index: int):
        """Check if the main view's stretch index has changed"""
        try:
            # Get the current stretch index from the main view
            main_stretch_index = self._get_main_view_stretch_index(image_index)

            if main_stretch_index is not None:
                # Get the last known index
                if image_index in self._stretch_monitors:
                    last_index = self._stretch_monitors[image_index]["last_stretch_index"]

                    # Check if it changed
                    if last_index != main_stretch_index:
                        logger.debug(
                            f"Detected stretch index change for image {image_index}: {last_index} -> {main_stretch_index}"
                        )

                        # Update our record
                        self._stretch_monitors[image_index][
                            "last_stretch_index"
                        ] = main_stretch_index

                        # Synchronize the dual view
                        self._synchronize_stretch_index(image_index, main_stretch_index)
                    # REMOVE the else clause that was logging every check

        except Exception as e:
            logger.error(
                f"Error checking stretch index change for image {image_index}: {e}"
            )

    def _synchronize_stretch_index(self, image_index: int, new_stretch_index: int):
        """Synchronize the dual view's stretch index with the main view"""
        try:
            dual_raster_view = self._raster_views.get(image_index)

            if dual_raster_view and hasattr(dual_raster_view, "viewModel"):
                current_index = dual_raster_view.viewModel.stretchIndex

                if current_index != new_stretch_index:
                    logger.debug(
                        f"Synchronizing stretch index for image {image_index}: {current_index} -> {new_stretch_index}"
                    )

                    # Update the dual view's stretch index
                    dual_raster_view.viewModel.stretchIndex = new_stretch_index

                    # Force a refresh with the new stretch
                    self._force_stretch_update(dual_raster_view, image_index)

        except Exception as e:
            logger.error(
                f"Error synchronizing stretch index for image {image_index}: {e}"
            )

    def _on_viewmodel_stretch_changed(self, image_index: int):
        """Handle stretch changes from the ViewModel directly"""
        logger.debug(
            f"=== DUAL VIEW: ViewModel stretch changed for image {image_index} ==="
        )

        try:
            raster_view = self._raster_views.get(image_index)
            if raster_view:
                logger.debug(
                    f"Found raster view for image {image_index}, forcing refresh"
                )
                self._force_stretch_update(raster_view, image_index)
            else:
                logger.error(f"No raster view found for image {image_index}")
        except Exception as e:
            logger.error(
                f"Error handling ViewModel stretch change for image {image_index}: {e}"
            )

    def _on_viewmodel_band_changed(self, image_index: int):
        """Handle band changes from the ViewModel directly"""
        logger.debug(f"=== DUAL VIEW: ViewModel band changed for image {image_index} ===")

        try:
            raster_view = self._raster_views.get(image_index)
            if raster_view:
                logger.debug(
                    f"Found raster view for image {image_index}, forcing refresh"
                )
                self._force_stretch_update(raster_view, image_index)
            else:
                logger.error(f"No raster view found for image {image_index}")
        except Exception as e:
            logger.error(
                f"Error handling ViewModel band change for image {image_index}: {e}"
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

    def _on_stretch_changed(self, image_index: int):
        """Handle stretch changes for an image in dual view"""
        try:
            logger.debug(f"Stretch changed for image {image_index} in dual view")

            # Get the raster view for this image
            raster_view = self._raster_views.get(image_index)
            if raster_view:
                # Force the view to update its display with new stretch values
                raster_view._onStretchChanged()

                # Also update the view containers to reflect the change
                if image_index == self._primary_index:
                    self._update_primary_display()
                elif image_index == self._secondary_index:
                    self._update_secondary_display()

        except Exception as e:
            logger.error(f"Error handling stretch change for image {image_index}: {e}")

    def _on_band_changed(self, image_index: int):
        """Handle band changes for an image in dual view"""
        try:
            logger.debug(f"Band changed for image {image_index} in dual view")

            # Get the raster view for this image
            raster_view = self._raster_views.get(image_index)
            if raster_view:
                # Force the view to update its display with new band configuration
                raster_view._onBandChanged()

                # Also update the view containers to reflect the change
                if image_index == self._primary_index:
                    self._update_primary_display()
                elif image_index == self._secondary_index:
                    self._update_secondary_display()

        except Exception as e:
            logger.error(f"Error handling band change for image {image_index}: {e}")

    def _update_primary_display(self):
        """Update the primary image display"""
        if self._primary_index is not None:
            raster_view = self._raster_views.get(self._primary_index)
            if raster_view:
                # Force a refresh of the display
                raster_view.update()

    def _update_secondary_display(self):
        """Update the secondary image display"""
        if self._secondary_index is not None:
            raster_view = self._raster_views.get(self._secondary_index)
            if raster_view:
                # Force a refresh of the display
                raster_view.update()

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
