"""
A dialog for editing image metadata after loading.
"""

import logging
import numpy as np
from PyQt6.QtWidgets import (
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTabWidget,
    QWidget,
    QFormLayout,
    QTableWidget,
    QTableWidgetItem,
    QDialogButtonBox,
    QComboBox,
    QSpinBox,
    QCheckBox,
    QMessageBox,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDoubleValidator

from varda.common.entities import Metadata, Band
from varda.project import ProjectContext

logger = logging.getLogger(__name__)


class MetadataEditor(QWidget):
    """
    Dialog for editing image metadata after loading.

    This dialog allows users to edit various metadata fields after an image has been
    loaded, particularly useful when metadata couldn't be properly extracted from the file.
    """

    metadataUpdated = pyqtSignal(Metadata)

    def __init__(self, proj: ProjectContext = None, imageIndex=None, parent=None):
        super().__init__(parent)
        self.proj = proj
        self.imageIndex = imageIndex
        self.metadata = proj.getImage(imageIndex).metadata

        self.initUI()

    def initUI(self):
        self.setWindowTitle("Metadata Editor")
        self.resize(600, 500)

        # Create tabs for different categories of metadata
        self.tabWidget = QTabWidget()

        # Create the tabs
        self.generalTab = QWidget()
        self.wavelengthsTab = QWidget()
        self.bandsTab = QWidget()
        self.extraTab = QWidget()

        # Setup the tabs
        self.setupGeneralTab()
        self.setupWavelengthsTab()
        self.setupBandsTab()
        self.setupExtraTab()

        # Add the tabs to the tab widget
        self.tabWidget.addTab(self.generalTab, "General")
        self.tabWidget.addTab(self.wavelengthsTab, "Wavelengths")
        self.tabWidget.addTab(self.bandsTab, "Bands")
        self.tabWidget.addTab(self.extraTab, "Extra Metadata")

        # Buttons
        self.buttonBox = QDialogButtonBox(QDialogButtonBox.StandardButton.Save)
        self.buttonBox.accepted.connect(self.onSave)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Edit metadata properties:"))
        layout.addWidget(self.tabWidget)
        layout.addWidget(self.buttonBox)
        self.setLayout(layout)

    def setupGeneralTab(self):
        """Setup the general metadata tab with basic image information."""
        layout = QFormLayout()
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        # Filename (read-only)
        self.filepathEdit = QLineEdit(self.metadata.filePath)
        self.filepathEdit.setReadOnly(True)
        layout.addRow("File Path:", self.filepathEdit)

        # Driver
        self.driverEdit = QLineEdit(self.metadata.driver)
        layout.addRow("Driver:", self.driverEdit)

        # Dimensions
        self.widthEdit = QSpinBox()
        self.widthEdit.setRange(1, 100000)
        self.widthEdit.setValue(self.metadata.width)
        layout.addRow("Width:", self.widthEdit)

        self.heightEdit = QSpinBox()
        self.heightEdit.setRange(1, 100000)
        self.heightEdit.setValue(self.metadata.height)
        layout.addRow("Height:", self.heightEdit)

        # Band Count
        self.bandCountEdit = QSpinBox()
        self.bandCountEdit.setRange(1, 10000)
        self.bandCountEdit.setValue(self.metadata.bandCount)
        self.bandCountEdit.valueChanged.connect(self.onBandCountChanged)
        layout.addRow("Band Count:", self.bandCountEdit)

        # Data Type
        self.dtypeEdit = QLineEdit(self.metadata.dtype)
        layout.addRow("Data Type:", self.dtypeEdit)

        # NoData Value
        self.nodataEdit = QLineEdit(str(self.metadata.dataIgnore))
        self.nodataEdit.setValidator(QDoubleValidator())
        layout.addRow("NoData Value:", self.nodataEdit)

        # Apply layout to tab
        self.generalTab.setLayout(layout)

    def setupWavelengthsTab(self):
        """Setup the wavelengths tab with the wavelength values."""
        layout = QVBoxLayout()

        # Wavelength type selection
        typeLayout = QHBoxLayout()
        typeLayout.addWidget(QLabel("Wavelength Type:"))

        self.wavelengthTypeCombo = QComboBox()
        self.wavelengthTypeCombo.addItems(["Float", "Integer", "String"])

        # Set current type based on metadata
        if self.metadata.wavelengths_type == float:
            self.wavelengthTypeCombo.setCurrentIndex(0)
        elif self.metadata.wavelengths_type == int:
            self.wavelengthTypeCombo.setCurrentIndex(1)
        else:
            self.wavelengthTypeCombo.setCurrentIndex(2)

        typeLayout.addWidget(self.wavelengthTypeCombo)
        typeLayout.addStretch()
        layout.addLayout(typeLayout)

        # Option to generate sequence
        genLayout = QHBoxLayout()

        self.genWavelengthsCheck = QCheckBox("Generate wavelength sequence")
        genLayout.addWidget(self.genWavelengthsCheck)

        self.genStartEdit = QLineEdit("400")
        self.genStartEdit.setValidator(QDoubleValidator())
        self.genStartEdit.setFixedWidth(80)
        genLayout.addWidget(QLabel("Start:"))
        genLayout.addWidget(self.genStartEdit)

        self.genStepEdit = QLineEdit("10")
        self.genStepEdit.setValidator(QDoubleValidator())
        self.genStepEdit.setFixedWidth(80)
        genLayout.addWidget(QLabel("Step:"))
        genLayout.addWidget(self.genStepEdit)

        self.genButton = QPushButton("Generate")
        self.genButton.clicked.connect(self.generateWavelengths)
        genLayout.addWidget(self.genButton)

        layout.addLayout(genLayout)

        # Wavelength table
        self.wavelengthTable = QTableWidget()
        self.wavelengthTable.setColumnCount(2)
        self.wavelengthTable.setHorizontalHeaderLabels(["Index", "Wavelength"])

        # Populate table with current wavelengths
        self.updateWavelengthTable()

        layout.addWidget(self.wavelengthTable)

        # Apply layout to tab
        self.wavelengthsTab.setLayout(layout)

    def updateWavelengthTable(self):
        """Update the wavelength table with current values."""
        self.wavelengthTable.setRowCount(self.metadata.bandCount)

        for i in range(self.metadata.bandCount):
            # Index column
            indexItem = QTableWidgetItem(str(i))
            indexItem.setFlags(indexItem.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.wavelengthTable.setItem(i, 0, indexItem)

            # Wavelength column - get value safely
            if i < len(self.metadata.wavelengths):
                wavelengthValue = str(self.metadata.wavelengths[i])
            else:
                wavelengthValue = str(i)

            wavelengthItem = QTableWidgetItem(wavelengthValue)
            self.wavelengthTable.setItem(i, 1, wavelengthItem)

    def setupBandsTab(self):
        """Setup the bands tab with the band configurations."""
        layout = QVBoxLayout()

        # Band table
        self.bandTable = QTableWidget()
        self.bandTable.setColumnCount(4)
        self.bandTable.setHorizontalHeaderLabels(
            ["Name", "Red Channel", "Green Channel", "Blue Channel"]
        )

        # Get bands from the metadata
        bands = []
        if hasattr(self.metadata, "defaultBand") and self.metadata.defaultBand:
            bands.append(self.metadata.defaultBand)

        # If this is from an existing image, get all bands
        if self.proj and self.imageIndex is not None:
            bands = self.proj.getImage(self.imageIndex).band

        # If no bands, create a default one
        if not bands:
            bands = [Band.createDefault()]

        # Populate table with bands
        self.bandTable.setRowCount(len(bands))

        for i, band in enumerate(bands):
            self.bandTable.setItem(i, 0, QTableWidgetItem(band.name))
            self.bandTable.setItem(i, 1, QTableWidgetItem(str(band.r)))
            self.bandTable.setItem(i, 2, QTableWidgetItem(str(band.g)))
            self.bandTable.setItem(i, 3, QTableWidgetItem(str(band.b)))

        layout.addWidget(self.bandTable)

        # Buttons for band management
        buttonLayout = QHBoxLayout()

        self.addBandButton = QPushButton("Add Band")
        self.addBandButton.clicked.connect(self.addBand)
        buttonLayout.addWidget(self.addBandButton)

        self.removeBandButton = QPushButton("Remove Band")
        self.removeBandButton.clicked.connect(self.removeBand)
        buttonLayout.addWidget(self.removeBandButton)

        layout.addLayout(buttonLayout)

        # Apply layout to tab
        self.bandsTab.setLayout(layout)

    def setupExtraTab(self):
        """Setup the extra metadata tab with any additional metadata."""
        layout = QVBoxLayout()

        # Extra metadata table
        self.extraTable = QTableWidget()
        self.extraTable.setColumnCount(2)
        self.extraTable.setHorizontalHeaderLabels(["Key", "Value"])

        # Populate table with extra metadata
        items = list(self.metadata.extraMetadata.items())
        self.extraTable.setRowCount(len(items))

        for i, (key, value) in enumerate(items):
            self.extraTable.setItem(i, 0, QTableWidgetItem(key))
            self.extraTable.setItem(i, 1, QTableWidgetItem(str(value)))

        layout.addWidget(self.extraTable)

        # Buttons for extra metadata management
        buttonLayout = QHBoxLayout()

        self.addExtraButton = QPushButton("Add Field")
        self.addExtraButton.clicked.connect(self.addExtraField)
        buttonLayout.addWidget(self.addExtraButton)

        self.removeExtraButton = QPushButton("Remove Field")
        self.removeExtraButton.clicked.connect(self.removeExtraField)
        buttonLayout.addWidget(self.removeExtraButton)

        layout.addLayout(buttonLayout)

        # Apply layout to tab
        self.extraTab.setLayout(layout)

    def onBandCountChanged(self, value):
        """Handle changes to the band count."""
        # Update wavelength table
        self.updateWavelengthTable()

    def generateWavelengths(self):
        """Generate a sequence of wavelengths based on user input."""
        try:
            start = float(self.genStartEdit.text())
            step = float(self.genStepEdit.text())
            count = self.bandCountEdit.value()

            wavelengths = [start + i * step for i in range(count)]

            # Update the table
            for i in range(min(count, self.wavelengthTable.rowCount())):
                self.wavelengthTable.setItem(
                    i, 1, QTableWidgetItem(str(wavelengths[i]))
                )

            # If the table has fewer rows than the new count, add more
            if self.wavelengthTable.rowCount() < count:
                self.updateWavelengthTable()

        except ValueError as e:
            QMessageBox.warning(
                self, "Input Error", f"Invalid input for wavelength generation: {e}"
            )

    def addBand(self):
        """Add a new band to the band table."""
        currentRows = self.bandTable.rowCount()
        self.bandTable.setRowCount(currentRows + 1)

        # Use sensible defaults for new band
        r, g, b = 0, 0, 0
        if self.bandCountEdit.value() >= 3:
            r, g, b = 0, 1, 2

        self.bandTable.setItem(currentRows, 0, QTableWidgetItem(f"Band {currentRows}"))
        self.bandTable.setItem(currentRows, 1, QTableWidgetItem(str(r)))
        self.bandTable.setItem(currentRows, 2, QTableWidgetItem(str(g)))
        self.bandTable.setItem(currentRows, 3, QTableWidgetItem(str(b)))

    def removeBand(self):
        """Remove the selected band from the band table."""
        selectedItems = self.bandTable.selectedItems()
        if not selectedItems:
            return

        selectedRow = selectedItems[0].row()
        self.bandTable.removeRow(selectedRow)

    def addExtraField(self):
        """Add a new field to the extra metadata table."""
        currentRows = self.extraTable.rowCount()
        self.extraTable.setRowCount(currentRows + 1)

        self.extraTable.setItem(currentRows, 0, QTableWidgetItem("new_key"))
        self.extraTable.setItem(currentRows, 1, QTableWidgetItem("new_value"))

    def removeExtraField(self):
        """Remove the selected field from the extra metadata table."""
        selectedItems = self.extraTable.selectedItems()
        if not selectedItems:
            return

        selectedRow = selectedItems[0].row()
        self.extraTable.removeRow(selectedRow)

    def onSave(self):
        """Save the edited metadata."""
        try:
            # Get general metadata
            metadata_dict = {
                "filePath": self.filepathEdit.text(),
                "driver": self.driverEdit.text(),
                "width": self.widthEdit.value(),
                "height": self.heightEdit.value(),
                "bandCount": self.bandCountEdit.value(),
                "dtype": self.dtypeEdit.text(),
                "dataIgnore": float(self.nodataEdit.text()),
            }

            # Get wavelengths
            wavelengths = []
            wavelength_type = [float, int, str][self.wavelengthTypeCombo.currentIndex()]

            for i in range(self.wavelengthTable.rowCount()):
                item = self.wavelengthTable.item(i, 1)
                if item:
                    value = item.text()
                    try:
                        if wavelength_type == float:
                            wavelengths.append(float(value))
                        elif wavelength_type == int:
                            wavelengths.append(int(value))
                        else:
                            wavelengths.append(str(value))
                    except ValueError:
                        # Fall back to string if conversion fails
                        wavelengths.append(str(value))

            metadata_dict["wavelengths"] = np.array(wavelengths)
            metadata_dict["wavelengths_type"] = wavelength_type

            # Get bands
            bands = []
            for i in range(self.bandTable.rowCount()):
                name = self.bandTable.item(i, 0).text()
                r = int(self.bandTable.item(i, 1).text())
                g = int(self.bandTable.item(i, 2).text())
                b = int(self.bandTable.item(i, 3).text())
                bands.append(Band(name, r, g, b))

            if bands:
                metadata_dict["defaultBand"] = bands[0]

            # Get extra metadata
            extraMetadata = {}
            for i in range(self.extraTable.rowCount()):
                key = self.extraTable.item(i, 0).text()
                value = self.extraTable.item(i, 1).text()
                extraMetadata[key] = value

            metadata_dict["extraMetadata"] = extraMetadata

            # Create new metadata object
            updated_metadata = Metadata(**metadata_dict)

            # If this is for an existing image in a project
            if self.proj and self.imageIndex is not None:
                for key, value in metadata_dict.items():
                    if key != "extraMetadata":
                        self.proj.updateMetadata(self.imageIndex, key, value)

                # Handle bands separately (clear existing and add new ones)
                image = self.proj.getImage(self.imageIndex)
                for i, band in enumerate(bands):
                    if i < len(image.band):
                        self.proj.updateBand(
                            self.imageIndex,
                            i,
                            name=band.name,
                            r=band.r,
                            g=band.g,
                            b=band.b,
                        )
                    else:
                        self.proj.addBand(self.imageIndex, band)

                # Update extra metadata
                for key, value in extraMetadata.items():
                    self.proj.updateMetadata(self.imageIndex, key, value)

            # Emit the updated metadata
            self.metadataUpdated.emit(updated_metadata)

            self.accept()

        except Exception as e:
            logger.error(f"Error saving metadata: {e}")
            QMessageBox.critical(self, "Error", f"Failed to save metadata: {str(e)}")
