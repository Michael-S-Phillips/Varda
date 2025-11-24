"""
Dual Image Selection Dialog

Dialog for selecting two images to link in dual view mode.
"""

import logging
from typing import Optional, Tuple
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QGroupBox,
    QRadioButton,
    QButtonGroup,
    QCheckBox,
    QSpinBox,
    QSlider,
    QFormLayout,
    QDialogButtonBox,
    QApplication,
)

from varda.workspaces.dual_image_view.dual_image_types import (
    DualImageConfig,
    DualImageMode,
    LinkType,
)
import varda

logger = logging.getLogger(__name__)


class DualImageSelectionDialog(QDialog):
    """
    Dialog for selecting images and configuring dual image view settings.
    """

    def __init__(self, imageList, parent=None):
        super().__init__(parent)
        self.imageList = imageList
        self.config = DualImageConfig()

        # UI components
        self.primaryCombo = None
        self.secondaryCombo = None
        self.modeGroup = None
        self.linkTypeGroup = None
        self.opacitySlider = None
        self.blinkIntervalSpin = None
        self.syncNavigationCb = None
        self.syncRoisCb = None

        self._initUI()
        self._populateImageLists()
        self._connectSignals()

        logger.debug("DualImageSelectionDialog initialized")

    def _initUI(self):
        """Initialize the user interface"""
        self.setWindowTitle("Dual Image View Setup")
        self.setModal(True)
        self.resize(400, 500)

        layout = QVBoxLayout(self)

        # Image selection
        imageGroup = self._createImageSelectionGroup()
        layout.addWidget(imageGroup)

        # Link type selection
        linkTypeGroup = self._createLinkTypeGroup()
        layout.addWidget(linkTypeGroup)

        # Display mode selection
        modeGroup = self._create_mode_group()
        layout.addWidget(modeGroup)

        # Overlay settings
        overlayGroup = self._create_overlay_group()
        layout.addWidget(overlayGroup)

        # Blink settings
        blinkGroup = self._create_blink_group()
        layout.addWidget(blinkGroup)

        # Synchronization settings
        syncGroup = self._create_sync_group()
        layout.addWidget(syncGroup)

        # Dialog buttons
        buttonBox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)
        layout.addWidget(buttonBox)

    def _createImageSelectionGroup(self) -> QGroupBox:
        """Create image selection controls"""
        group = QGroupBox("Image Selection")
        layout = QFormLayout(group)

        # Primary image
        self.primaryCombo = QComboBox()
        self.primaryCombo.setToolTip("Select the primary (reference) image")
        layout.addRow("Primary Image:", self.primaryCombo)

        # Secondary image
        self.secondaryCombo = QComboBox()
        self.secondaryCombo.setToolTip("Select the secondary image to compare")
        layout.addRow("Secondary Image:", self.secondaryCombo)

        return group

    def _createLinkTypeGroup(self) -> QGroupBox:
        """Create link type selection controls"""
        group = QGroupBox("Link Type")
        layout = QVBoxLayout(group)

        self.linkTypeGroup = QButtonGroup(self)

        # Pixel-based linking - use integer IDs instead of enum values
        pixelRadio = QRadioButton("Pixel-based (same extent)")
        pixelRadio.setToolTip(
            "Link images pixel-to-pixel (assumes same geographic extent)"
        )
        pixelRadio.setChecked(True)
        self.linkTypeGroup.addButton(pixelRadio, 0)  # Use 0 for pixel-based
        layout.addWidget(pixelRadio)

        # Geospatial linking
        geoRadio = QRadioButton("Geospatial coordinates")
        geoRadio.setToolTip("Link images by geographic coordinates")
        self.linkTypeGroup.addButton(geoRadio, 1)  # Use 1 for geospatial
        layout.addWidget(geoRadio)

        return group

    def _create_mode_group(self) -> QGroupBox:
        """Create display mode selection controls"""
        group = QGroupBox("Display Mode")
        layout = QVBoxLayout(group)

        self.modeGroup = QButtonGroup(self)

        # Side by side
        side_by_side_radio = QRadioButton("Side by Side")
        side_by_side_radio.setToolTip("Display images side by side")
        side_by_side_radio.setChecked(True)
        self.modeGroup.addButton(side_by_side_radio, 0)  # Use 0 for side-by-side
        layout.addWidget(side_by_side_radio)

        # Overlay
        overlay_radio = QRadioButton("Overlay")
        overlay_radio.setToolTip("Overlay secondary image on primary")
        self.modeGroup.addButton(overlay_radio, 1)  # Use 1 for overlay
        layout.addWidget(overlay_radio)

        # Blink
        blink_radio = QRadioButton("Blink")
        blink_radio.setToolTip("Alternate between images")
        self.modeGroup.addButton(blink_radio, 2)  # Use 2 for blink
        layout.addWidget(blink_radio)

        return group

    def _create_overlay_group(self) -> QGroupBox:
        """Create overlay settings controls"""
        group = QGroupBox("Overlay Settings")
        layout = QFormLayout(group)

        # Opacity slider
        self.opacitySlider = QSlider(Qt.Orientation.Horizontal)
        self.opacitySlider.setMinimum(0)
        self.opacitySlider.setMaximum(100)
        self.opacitySlider.setValue(50)
        self.opacitySlider.setToolTip("Adjust overlay transparency")

        opacityLayout = QHBoxLayout()
        self.opacityLabel = QLabel("50%")
        opacityLayout.addWidget(self.opacitySlider)
        opacityLayout.addWidget(self.opacityLabel)

        layout.addRow("Opacity:", opacityLayout)

        return group

    def _create_blink_group(self) -> QGroupBox:
        """Create blink settings controls"""
        group = QGroupBox("Blink Settings")
        layout = QFormLayout(group)

        # Blink interval
        self.blinkIntervalSpin = QSpinBox()
        self.blinkIntervalSpin.setMinimum(100)
        self.blinkIntervalSpin.setMaximum(5000)
        self.blinkIntervalSpin.setValue(1000)
        self.blinkIntervalSpin.setSuffix(" ms")
        self.blinkIntervalSpin.setToolTip("Time between blinks in milliseconds")

        layout.addRow("Interval:", self.blinkIntervalSpin)

        return group

    def _create_sync_group(self) -> QGroupBox:
        """Create synchronization settings controls"""
        group = QGroupBox("Synchronization")
        layout = QVBoxLayout(group)

        # Sync navigation
        self.syncNavigationCb = QCheckBox("Synchronize navigation (pan/zoom)")
        self.syncNavigationCb.setChecked(True)
        self.syncNavigationCb.setToolTip("Keep navigation synchronized between images")
        layout.addWidget(self.syncNavigationCb)

        # Sync ROIs
        self.syncRoisCb = QCheckBox("Synchronize ROIs")
        self.syncRoisCb.setChecked(True)
        self.syncRoisCb.setToolTip("Share ROIs between linked images")
        layout.addWidget(self.syncRoisCb)

        return group

    def _populateImageLists(self):
        """Populate the image selection combo boxes"""
        for i, image in enumerate(self.imageList):
            # Get image name for display
            display_name = self._get_image_display_name(image, i)

            self.primaryCombo.addItem(display_name, i)
            self.secondaryCombo.addItem(display_name, i)

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

    def _connectSignals(self):
        """Connect UI signals"""
        self.primaryCombo.currentIndexChanged.connect(self._on_primary_changed)
        self.secondaryCombo.currentIndexChanged.connect(self._on_secondary_changed)
        self.opacitySlider.valueChanged.connect(
            lambda value: self.opacityLabel.setText(f"{value}%")
        )

    def _on_primary_changed(self, index):
        """Handle primary image selection change"""
        # Ensure primary and secondary are different
        if self.secondaryCombo.currentIndex() == index:
            # Find a different secondary
            for i in range(self.secondaryCombo.count()):
                if i != index:
                    self.secondaryCombo.setCurrentIndex(i)
                    break

    def _on_secondary_changed(self, index):
        """Handle secondary image selection change"""
        # Ensure primary and secondary are different
        if self.primaryCombo.currentIndex() == index:
            # Find a different primary
            for i in range(self.primaryCombo.count()):
                if i != index:
                    self.primaryCombo.setCurrentIndex(i)
                    break

    def get_selected_images(self) -> Tuple[Optional[int], Optional[int]]:
        """Get the selected primary and secondary image indices"""
        primary_index = self.primaryCombo.currentData()
        secondary_index = self.secondaryCombo.currentData()
        return primary_index, secondary_index

    def get_configuration(self) -> DualImageConfig:
        """Get the configured dual image settings"""
        config = DualImageConfig()

        # Display mode based on button group ID
        modeId = self.modeGroup.checkedId()
        if modeId == 0:
            config.mode = DualImageMode.SIDE_BY_SIDE
        elif modeId == 1:
            config.mode = DualImageMode.OVERLAY
        elif modeId == 2:
            config.mode = DualImageMode.BLINK
        else:
            config.mode = DualImageMode.SIDE_BY_SIDE  # Default

        # Link type based on button group ID
        linkTypeId = self.linkTypeGroup.checkedId()
        if linkTypeId == 0:
            config.link_type = LinkType.PIXEL_BASED
        elif linkTypeId == 1:
            config.link_type = LinkType.GEOSPATIAL
        else:
            config.link_type = LinkType.PIXEL_BASED  # Default

        # Other settings
        config.overlay_opacity = self.opacitySlider.value() / 100.0
        config.blink_interval = self.blinkIntervalSpin.value()
        config.sync_navigation = self.syncNavigationCb.isChecked()
        config.sync_rois = self.syncRoisCb.isChecked()

        return config

    def set_default_images(
        self, primary_index: Optional[int] = None, secondary_index: Optional[int] = None
    ):
        """Set default image selections"""
        if primary_index is not None and primary_index < self.primaryCombo.count():
            self.primaryCombo.setCurrentIndex(primary_index)

        if (
            secondary_index is not None
            and secondary_index < self.secondaryCombo.count()
        ):
            self.secondaryCombo.setCurrentIndex(secondary_index)


if __name__ == "__main__":
    qapp = QApplication([])
    imageList = [
        varda.utilities.debug.generate_random_image((100, 100, 10), (10, 10, 10))
        for i in range(5)
    ]
    dialog = DualImageSelectionDialog(imageList)
    dialog.show()
    qapp.exec()
