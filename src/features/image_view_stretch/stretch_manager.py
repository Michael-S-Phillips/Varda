# src/features/image_view_stretch/stretch_manager.py
# Existing file to be modified

# standard library
import logging

# third party imports
from PyQt6.QtCore import pyqtSlot, Qt, QSize
from PyQt6.QtGui import QDoubleValidator
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTableWidget,
    QAbstractItemView,
    QTableWidgetItem,
    QPushButton,
    QSizePolicy,
    QStyledItemDelegate,
    QLineEdit,
    QHeaderView,
    QHBoxLayout,
    QLayout, QStyle, QToolButton,
    QGroupBox, QLabel, QMessageBox, QDialog,
)

# local imports
from core.data import ProjectContext
from features.image_view_histogram import getHistogramView
from core.stretch.stretch_manager import StretchPresets
from features.image_view_stretch.custom_stretch_dialog import CustomStretchDialog

logger = logging.getLogger(__name__)

class StretchManager(QWidget):
    """A widget to display a list of all the stretches associated with an image, and manage them.

    This includes being able to create, delete, and modify stretch configurations.
    Each stretch has a name, and minimum/maximum values for R, G, and B channels.
    """

    def __init__(self, proj: ProjectContext, imageIndex: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Stretch Manager")
        self.proj = proj
        self.imageIndex = imageIndex
        self.disableProjectUpdating = False
        self._handling_change = False  # Add recursion guard
        self._initUI()
        self._connectSignals()
        self._populateTable()

    def _initUI(self):
        self.table = QTableWidget(self)
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(
            ["Name", "minR", "maxR", "minG", "maxG", "minB", "maxB"]
        )

        # Set float delegates for all numeric columns
        for col in range(1, 7):
            self.table.setItemDelegateForColumn(col, self.FloatDelegate(self))

        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )

        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.AnyKeyPressed
            | QAbstractItemView.EditTrigger.DoubleClicked
        )
        self.toggleButton = QToolButton(self)
        self.toggleButton.setText("Show/Hide Table")
        self.toggleButton.setCheckable(True)
        self.toggleButton.setChecked(True)
        self.toggleButton.setArrowType(Qt.ArrowType.DownArrow)
        self.toggleButton.setFixedSize(15, 15)

        self.addButton = QPushButton("Add Stretch", self)
        self.addButton.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self.deleteButton = QPushButton("Delete Stretch", self)
        self.deleteButton.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )

        self.buttonLayout = QHBoxLayout()
        self.buttonLayout.addWidget(self.addButton)
        self.buttonLayout.addStretch()  # pushes the buttons apart from each other
        self.buttonLayout.addWidget(self.deleteButton)

        self.histogramView = getHistogramView(self.proj, self.imageIndex, self)

        # Add a section for preset stretches
        self.presetsGroup = QGroupBox("Preset Stretches", self)
        self.presetsLayout = QVBoxLayout()
        
        # Create a button for each preset
        self.presetButtons = {}
        for preset_id, preset_name in StretchPresets.get_preset_names():
            button = QPushButton(preset_name, self)
            button.clicked.connect(lambda checked, pid=preset_id: self._onPresetClicked(pid))
            self.presetsLayout.addWidget(button)
            self.presetButtons[preset_id] = button
        
        # Add a button for custom stretches
        self.customStretchButton = QPushButton("Custom Stretch...", self)
        self.customStretchButton.clicked.connect(self._onCustomStretchClicked)
        self.presetsLayout.addWidget(self.customStretchButton)
        
        # Add a button to create all preset stretches
        self.createAllPresetsButton = QPushButton("Create All Presets", self)
        self.createAllPresetsButton.clicked.connect(self._onCreateAllPresetsClicked)
        self.presetsLayout.addWidget(self.createAllPresetsButton)
        
        self.presetsGroup.setLayout(self.presetsLayout)

        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.toggleButton)
        self.layout.addLayout(self.buttonLayout)
        self.layout.addWidget(self.table)
        self.layout.addWidget(self.presetsGroup)  # Add the presets group
        self.layout.addWidget(self.histogramView)

        self.setLayout(self.layout)

    def _connectSignals(self):
        self.table.itemSelectionChanged.connect(self._onRowSelected)
        self.table.itemChanged.connect(self._onItemChanged)
        self.toggleButton.clicked.connect(self._toggleTable)
        self.addButton.clicked.connect(self._onAddButtonPressed)
        self.deleteButton.clicked.connect(self._onDeleteButtonPressed)
        self.proj.sigDataChanged.connect(self._onProjectDataChanged)

    def _populateTable(self):
        self.disableProjectUpdating = True
        stretches = self.proj.getImage(self.imageIndex).stretch
        self.table.setRowCount(len(stretches))

        for row, stretch in enumerate(stretches):
            self.table.setItem(row, 0, QTableWidgetItem(stretch.name))
            self.table.setItem(row, 1, QTableWidgetItem(str(stretch.minR)))
            self.table.setItem(row, 2, QTableWidgetItem(str(stretch.maxR)))
            self.table.setItem(row, 3, QTableWidgetItem(str(stretch.minG)))
            self.table.setItem(row, 4, QTableWidgetItem(str(stretch.maxG)))
            self.table.setItem(row, 5, QTableWidgetItem(str(stretch.minB)))
            self.table.setItem(row, 6, QTableWidgetItem(str(stretch.maxB)))
        self.disableProjectUpdating = False

    @pyqtSlot()
    def _toggleTable(self):
        if self.table.isVisible():
            self.table.hide()
            self.addButton.hide()
            self.deleteButton.hide()
            self.toggleButton.setArrowType(Qt.ArrowType.RightArrow)
        else:
            self.table.show()
            self.addButton.show()
            self.deleteButton.show()
            self.toggleButton.setArrowType(Qt.ArrowType.DownArrow)

    @pyqtSlot()
    def _onAddButtonPressed(self):
        """Add a new stretch configuration to the project."""
        self.proj.addStretch(self.imageIndex)
        # the project context will implicitly call _populateTable after updating

    @pyqtSlot()
    def _onDeleteButtonPressed(self):
        """Delete the selected stretch configuration from the project."""
        selected_items = self.table.selectedItems()
        if selected_items:
            row = selected_items[0].row()
            self.proj.removeStretch(self.imageIndex, row)
            # the project context will implicitly call _populateTable after updating

    @pyqtSlot(QTableWidgetItem)
    def _onItemChanged(self, item):
        if self.disableProjectUpdating:
            return

        row = item.row()
        column = item.column()
        value = item.text()

        # if updating name, we can stop here
        if column == 0:
            self.proj.updateStretch(self.imageIndex, row, name=value)
            return

        # For numeric values, convert to float
        floatVal = float(value)

        # Update the appropriate field based on column. Clamp the value based on the other field
        kwargs = {}

        if column == 1:
            minR = floatVal
            maxR = float(self.table.item(row, 2).text())
            clampedVal = min(minR, maxR)
            kwargs["minR"] = clampedVal
        elif column == 2:
            minR = float(self.table.item(row, 1).text())
            maxR = floatVal
            clampedVal = max(minR, maxR)
            kwargs["maxR"] = clampedVal

        elif column == 3:
            minG = floatVal
            maxG = float(self.table.item(row, 4).text())
            clampedVal = min(minG, maxG)
            kwargs["minG"] = clampedVal
        elif column == 4:
            minG = float(self.table.item(row, 3).text())
            maxG = floatVal
            clampedVal = max(minG, maxG)
            kwargs["maxG"] = clampedVal

        elif column == 5:
            minB = floatVal
            maxB = float(self.table.item(row, 6).text())
            clampedVal = min(minB, maxB)
            kwargs["minB"] = clampedVal
        elif column == 6:
            minB = float(self.table.item(row, 5).text())
            maxB = floatVal
            clampedVal = max(minB, maxB)
            kwargs["maxB"] = clampedVal

        self.proj.updateStretch(self.imageIndex, row, **kwargs)

    @pyqtSlot()
    def _onRowSelected(self):
        selectedItems = self.table.selectedItems()
        if selectedItems:
            row = selectedItems[0].row()
            print("row selected!", row)
            self.histogramView.viewModel.selectStretch(row)

    @pyqtSlot(int, ProjectContext.ChangeType)
    def _onProjectDataChanged(self, index, changeType):
        # Guard against recursion
        if self._handling_change:
            return
            
        if index == self.imageIndex and changeType is ProjectContext.ChangeType.STRETCH:
            self._handling_change = True
            try:
                self._populateTable()
            finally:
                self._handling_change = False
            
    def _onPresetClicked(self, preset_id):
        """Handle click on a preset stretch button."""
        try:
            # Get the image data
            image = self.proj.getImage(self.imageIndex)
            image_data = image.raster
            
            # Create a stretch from the preset
            stretch = StretchPresets.create_stretch_from_preset(preset_id, image_data)
            
            # Add the stretch to the project
            self.proj.addStretch(self.imageIndex, stretch)
            
            # Select the new stretch
            self.histogramView.viewModel.selectStretch(len(image.stretch) - 1)
            
        except Exception as e:
            logger.error(f"Error applying preset stretch {preset_id}: {e}")
            # Show an error message
            QMessageBox.warning(
                self, 
                "Stretch Error",
                f"Error applying stretch preset: {str(e)}",
                QMessageBox.StandardButton.Ok
            )
            
    def _onCustomStretchClicked(self):
        """Show dialog for creating a custom stretch."""
        dialog = CustomStretchDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            try:
                # Get the parameters from the dialog
                params = dialog.getParameters()
                algorithm_id = params.pop("algorithm_id", "percentile")
                
                # Get the image data
                image = self.proj.getImage(self.imageIndex)
                image_data = image.raster
                
                # Compute the stretch values
                from core.stretch.stretch_algorithms import compute_stretch
                minR, maxR, minG, maxG, minB, maxB = compute_stretch(
                    algorithm_id, image_data, **params)
                
                # Create a name for the stretch
                if algorithm_id == "percentile":
                    low = params.get("low_percentile", 2.0)
                    high = params.get("high_percentile", 98.0)
                    name = f"Percentile {low}% - {high}%"
                elif algorithm_id == "gaussian":
                    sigma = params.get("sigma_factor", 2.0)
                    name = f"Gaussian ±{sigma}σ"
                elif algorithm_id == "logarithmic":
                    gain = params.get("gain", 1.0)
                    name = f"Logarithmic (gain={gain})"
                elif algorithm_id == "decorrelation":
                    scaling = params.get("scaling_factor", 2.5)
                    name = f"Decorrelation (scale={scaling})"
                elif algorithm_id == "adaptive_eq":
                    clip = params.get("clip_limit", 0.01)
                    name = f"Adaptive Eq. (clip={clip})"
                else:
                    name = "Custom Stretch"
                
                # Create and add the stretch
                from core.entities.stretch import Stretch
                stretch = Stretch(name, minR, maxR, minG, maxG, minB, maxB)
                self.proj.addStretch(self.imageIndex, stretch)
                
                # Select the new stretch
                self.histogramView.viewModel.selectStretch(len(image.stretch) - 1)
                
            except Exception as e:
                logger.error(f"Error creating custom stretch: {e}")
                # Show an error message
                QMessageBox.warning(
                    self, 
                    "Stretch Error",
                    f"Error creating custom stretch: {str(e)}",
                    QMessageBox.StandardButton.Ok
                )
                
    def _onCreateAllPresetsClicked(self):
        """Create a stretch for each available preset."""
        try:
            # Get the image data
            image = self.proj.getImage(self.imageIndex)
            image_data = image.raster
            
            # Create stretches for all presets
            stretches = StretchPresets.create_all_preset_stretches(image_data)
            
            # Add each stretch to the project
            for stretch in stretches:
                self.proj.addStretch(self.imageIndex, stretch)
            
            # Select the first new stretch
            if stretches:
                self.histogramView.viewModel.selectStretch(
                    len(image.stretch) - len(stretches)
                )
                
        except Exception as e:
            logger.error(f"Error creating all preset stretches: {e}")
            # Show an error message
            QMessageBox.warning(
                self, 
                "Stretch Error",
                f"Error creating preset stretches: {str(e)}",
                QMessageBox.StandardButton.Ok
            )

    class FloatDelegate(QStyledItemDelegate):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.decimals = 3

        def createEditor(self, parent, option, index):
            editor = QLineEdit(parent)
            validator = QDoubleValidator()
            editor.setValidator(validator)
            return editor

        def displayText(self, value, locale):
            try:
                floatVal = float(value)
                return f"{floatVal:.{self.decimals}f}"
            except ValueError:
                return value

        # def sizeHint(self, option, index):
        #     size = super().sizeHint(option, index)
        #     if option.state & QStyle.StateFlag.State_Editing:
        #         size.setWidth(size.width() * 2)  # Expand the width when editing
        #     return size

        def updateEditorGeometry(self, editor, option, index):
            rect = option.rect
            # Expand the width; adjust the factor as needed
            rect.setWidth(rect.width() * 2)
            editor.setGeometry(rect)