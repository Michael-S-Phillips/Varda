"""
Dual Image Selection Dialog

Dialog for selecting two images to link in dual view mode.
"""

import logging
from typing import Optional, Tuple
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QGroupBox,
    QRadioButton,
    QButtonGroup,
    QCheckBox,
    QSpinBox,
    QSlider,
    QFormLayout,
    QDialogButtonBox,
)

from .dual_image_types import DualImageConfig, DualImageMode, LinkType
from varda.app.project import ProjectContext

logger = logging.getLogger(__name__)


class DualImageSelectionDialog(QDialog):
    """
    Dialog for selecting images and configuring dual image view settings.
    """

    def __init__(self, project_context: ProjectContext, parent=None):
        super().__init__(parent)
        self.proj = project_context
        self.config = DualImageConfig()

        # UI components
        self.primary_combo = None
        self.secondary_combo = None
        self.mode_group = None
        self.link_type_group = None
        self.opacity_slider = None
        self.blink_interval_spin = None
        self.sync_navigation_cb = None
        self.sync_rois_cb = None

        self._init_ui()
        self._populate_image_lists()
        self._connect_signals()

        logger.debug("DualImageSelectionDialog initialized")

    def _init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("Dual Image View Setup")
        self.setModal(True)
        self.resize(400, 500)

        layout = QVBoxLayout(self)

        # Image selection
        image_group = self._create_image_selection_group()
        layout.addWidget(image_group)

        # Link type selection
        link_type_group = self._create_link_type_group()
        layout.addWidget(link_type_group)

        # Display mode selection
        mode_group = self._create_mode_group()
        layout.addWidget(mode_group)

        # Overlay settings
        overlay_group = self._create_overlay_group()
        layout.addWidget(overlay_group)

        # Blink settings
        blink_group = self._create_blink_group()
        layout.addWidget(blink_group)

        # Synchronization settings
        sync_group = self._create_sync_group()
        layout.addWidget(sync_group)

        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _create_image_selection_group(self) -> QGroupBox:
        """Create image selection controls"""
        group = QGroupBox("Image Selection")
        layout = QFormLayout(group)

        # Primary image
        self.primary_combo = QComboBox()
        self.primary_combo.setToolTip("Select the primary (reference) image")
        layout.addRow("Primary Image:", self.primary_combo)

        # Secondary image
        self.secondary_combo = QComboBox()
        self.secondary_combo.setToolTip("Select the secondary image to compare")
        layout.addRow("Secondary Image:", self.secondary_combo)

        return group

    def _create_link_type_group(self) -> QGroupBox:
        """Create link type selection controls"""
        group = QGroupBox("Link Type")
        layout = QVBoxLayout(group)

        self.link_type_group = QButtonGroup(self)

        # Pixel-based linking - use integer IDs instead of enum values
        pixel_radio = QRadioButton("Pixel-based (same extent)")
        pixel_radio.setToolTip(
            "Link images pixel-to-pixel (assumes same geographic extent)"
        )
        pixel_radio.setChecked(True)
        self.link_type_group.addButton(pixel_radio, 0)  # Use 0 for pixel-based
        layout.addWidget(pixel_radio)

        # Geospatial linking
        geo_radio = QRadioButton("Geospatial coordinates")
        geo_radio.setToolTip("Link images by geographic coordinates")
        self.link_type_group.addButton(geo_radio, 1)  # Use 1 for geospatial
        layout.addWidget(geo_radio)

        return group

    def _create_mode_group(self) -> QGroupBox:
        """Create display mode selection controls"""
        group = QGroupBox("Display Mode")
        layout = QVBoxLayout(group)

        self.mode_group = QButtonGroup(self)

        # Side by side
        side_by_side_radio = QRadioButton("Side by Side")
        side_by_side_radio.setToolTip("Display images side by side")
        side_by_side_radio.setChecked(True)
        self.mode_group.addButton(side_by_side_radio, 0)  # Use 0 for side-by-side
        layout.addWidget(side_by_side_radio)

        # Overlay
        overlay_radio = QRadioButton("Overlay")
        overlay_radio.setToolTip("Overlay secondary image on primary")
        self.mode_group.addButton(overlay_radio, 1)  # Use 1 for overlay
        layout.addWidget(overlay_radio)

        # Blink
        blink_radio = QRadioButton("Blink")
        blink_radio.setToolTip("Alternate between images")
        self.mode_group.addButton(blink_radio, 2)  # Use 2 for blink
        layout.addWidget(blink_radio)

        return group

    def _create_overlay_group(self) -> QGroupBox:
        """Create overlay settings controls"""
        group = QGroupBox("Overlay Settings")
        layout = QFormLayout(group)

        # Opacity slider
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setMinimum(0)
        self.opacity_slider.setMaximum(100)
        self.opacity_slider.setValue(50)
        self.opacity_slider.setToolTip("Adjust overlay transparency")

        opacity_layout = QHBoxLayout()
        self.opacity_label = QLabel("50%")
        opacity_layout.addWidget(self.opacity_slider)
        opacity_layout.addWidget(self.opacity_label)

        layout.addRow("Opacity:", opacity_layout)

        return group

    def _create_blink_group(self) -> QGroupBox:
        """Create blink settings controls"""
        group = QGroupBox("Blink Settings")
        layout = QFormLayout(group)

        # Blink interval
        self.blink_interval_spin = QSpinBox()
        self.blink_interval_spin.setMinimum(100)
        self.blink_interval_spin.setMaximum(5000)
        self.blink_interval_spin.setValue(1000)
        self.blink_interval_spin.setSuffix(" ms")
        self.blink_interval_spin.setToolTip("Time between blinks in milliseconds")

        layout.addRow("Interval:", self.blink_interval_spin)

        return group

    def _create_sync_group(self) -> QGroupBox:
        """Create synchronization settings controls"""
        group = QGroupBox("Synchronization")
        layout = QVBoxLayout(group)

        # Sync navigation
        self.sync_navigation_cb = QCheckBox("Synchronize navigation (pan/zoom)")
        self.sync_navigation_cb.setChecked(True)
        self.sync_navigation_cb.setToolTip(
            "Keep navigation synchronized between images"
        )
        layout.addWidget(self.sync_navigation_cb)

        # Sync ROIs
        self.sync_rois_cb = QCheckBox("Synchronize ROIs")
        self.sync_rois_cb.setChecked(True)
        self.sync_rois_cb.setToolTip("Share ROIs between linked images")
        layout.addWidget(self.sync_rois_cb)

        return group

    def _populate_image_lists(self):
        """Populate the image selection combo boxes"""
        images = self.proj.getAllImages()

        for i, image in enumerate(images):
            # Get image name for display
            display_name = self._get_image_display_name(image, i)

            self.primary_combo.addItem(display_name, i)
            self.secondary_combo.addItem(display_name, i)

    def _get_image_display_name(self, image, index: int) -> str:
        """Get a display name for an image"""
        try:
            if hasattr(image.metadata, "name") and image.metadata.name:
                return f"{index}: {image.metadata.name}"
            elif hasattr(image.metadata, "filePath") and image.metadata.filePath:
                import os

                filename = os.path.basename(image.metadata.filePath)
                return f"{index}: {filename}"
            else:
                return f"Image {index}"
        except Exception:
            return f"Image {index}"

    def _connect_signals(self):
        """Connect UI signals"""
        self.primary_combo.currentIndexChanged.connect(self._on_primary_changed)
        self.secondary_combo.currentIndexChanged.connect(self._on_secondary_changed)
        self.opacity_slider.valueChanged.connect(self._on_opacity_changed)

    def _on_primary_changed(self, index):
        """Handle primary image selection change"""
        # Ensure primary and secondary are different
        if self.secondary_combo.currentIndex() == index:
            # Find a different secondary
            for i in range(self.secondary_combo.count()):
                if i != index:
                    self.secondary_combo.setCurrentIndex(i)
                    break

    def _on_secondary_changed(self, index):
        """Handle secondary image selection change"""
        # Ensure primary and secondary are different
        if self.primary_combo.currentIndex() == index:
            # Find a different primary
            for i in range(self.primary_combo.count()):
                if i != index:
                    self.primary_combo.setCurrentIndex(i)
                    break

    def _on_opacity_changed(self, value):
        """Handle opacity slider change"""
        self.opacity_label.setText(f"{value}%")

    def get_selected_images(self) -> Tuple[Optional[int], Optional[int]]:
        """Get the selected primary and secondary image indices"""
        primary_index = self.primary_combo.currentData()
        secondary_index = self.secondary_combo.currentData()
        return primary_index, secondary_index

    def get_configuration(self) -> DualImageConfig:
        """Get the configured dual image settings"""
        config = DualImageConfig()

        # Display mode based on button group ID
        mode_id = self.mode_group.checkedId()
        if mode_id == 0:
            config.mode = DualImageMode.SIDE_BY_SIDE
        elif mode_id == 1:
            config.mode = DualImageMode.OVERLAY
        elif mode_id == 2:
            config.mode = DualImageMode.BLINK
        else:
            config.mode = DualImageMode.SIDE_BY_SIDE  # Default

        # Link type based on button group ID
        link_type_id = self.link_type_group.checkedId()
        if link_type_id == 0:
            config.link_type = LinkType.PIXEL_BASED
        elif link_type_id == 1:
            config.link_type = LinkType.GEOSPATIAL
        else:
            config.link_type = LinkType.PIXEL_BASED  # Default

        # Other settings
        config.overlay_opacity = self.opacity_slider.value() / 100.0
        config.blink_interval = self.blink_interval_spin.value()
        config.sync_navigation = self.sync_navigation_cb.isChecked()
        config.sync_rois = self.sync_rois_cb.isChecked()

        return config

    def set_default_images(
        self, primary_index: Optional[int] = None, secondary_index: Optional[int] = None
    ):
        """Set default image selections"""
        if primary_index is not None and primary_index < self.primary_combo.count():
            self.primary_combo.setCurrentIndex(primary_index)

        if (
            secondary_index is not None
            and secondary_index < self.secondary_combo.count()
        ):
            self.secondary_combo.setCurrentIndex(secondary_index)
