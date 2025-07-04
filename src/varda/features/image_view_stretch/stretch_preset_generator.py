from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QGroupBox,
    QVBoxLayout,
    QComboBox,
    QPushButton,
    QLabel,
)

from varda.core.stretch import StretchPresets


class StretchPresetSelector(QWidget):

    sigStretchPresetApplied = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._initUI()

    def _initUI(self):
        # Add stretch preset options
        self.presetsGroup = QGroupBox("Preset Stretches")
        self.presetsLayout = QVBoxLayout()

        # Add a dropdown for selecting presets
        self.presetCombo = QComboBox()
        for _, preset_name in StretchPresets.get_preset_names():
            self.presetCombo.addItem(preset_name)

        self.applyPresetButton = QPushButton("Apply Selected Preset")
        self.applyPresetButton.clicked.connect(self._onApplyPresetClicked)

        self.presetsLayout.addWidget(QLabel("Select a preset stretch:"))
        self.presetsLayout.addWidget(self.presetCombo)
        self.presetsLayout.addWidget(self.applyPresetButton)

        self.presetsGroup.setLayout(self.presetsLayout)

        selectorLayout = QVBoxLayout()
        selectorLayout.addWidget(self.presetsGroup)

        layout = QVBoxLayout()
        layout.addLayout(selectorLayout)

    def _onApplyPresetClicked(self):
        """Apply the selected preset stretch."""
        preset_index = self.presetCombo.currentIndex()
        preset_id = StretchPresets.get_preset_names()[preset_index][0]

        self.sigStretchPresetApplied.emit(preset_id)

        try:
            # Get the selected preset
            preset_index = self.presetCombo.currentIndex()
            preset_id = StretchPresets.get_preset_names()[preset_index][0]

            # Get the image data and current band configuration
            image = self.proj.getImage(self.imageIndex)
            imageData = image.raster

            # Get the current band configuration for RGB channel selection
            current_band = self.viewModel.getSelectedBand()

            # Create a stretch from the preset using the current band configuration
            stretch = StretchPresets.create_stretch_from_preset(
                preset_id, imageData, current_band
            )

            # Add the stretch to the project
            self.viewModel.proj.addStretch(self.viewModel.index, stretch)

            # Select the new stretch
            self.viewModel.selectStretch(len(image.stretch) - 1)

        except Exception as e:
            logger.error(f"Error applying preset stretch: {e}")
            # Show an error message
            QMessageBox.warning(
                self,
                "Stretch Error",
                f"Error applying stretch preset: {str(e)}",
                QMessageBox.StandardButton.Ok,
            )
