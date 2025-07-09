import logging

import numpy as np
from PyQt6.QtCore import pyqtSlot, Qt, pyqtSignal
from PyQt6.QtGui import QIntValidator, QStandardItemModel
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
    QLayout,
    QToolButton,
    QComboBox,
    QCheckBox,
)

from varda.core.data import ProjectContext
from varda.core.entities import Band
from varda.features.components.band_management.image_view_band import getBandView

logger = logging.getLogger(__name__)


class BandManager(QWidget):
    """A widget to display a list of all the bands associated with an image, and manage them.

    This includes being able to create, delete, and rename bands.
    """

    sigBandChanged = pyqtSignal(Band)

    def __init__(self, proj: ProjectContext, imageIndex: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Band Manager")
        self.proj = proj
        self.imageIndex = imageIndex
        self.useWavelengthValues = False
        self.disableProjectUpdating = False
        self._initUI()
        self._connectSignals()
        self._populateTable()

        # Ensure the first band is selected by default and the band view is synchronized
        if self.table.rowCount() > 0:
            self.table.selectRow(0)
            self.bandView.viewModel.selectBand(0)

    def _initUI(self):
        self.modeToggle = QCheckBox("Use Wavelength Values", self)
        self.modeToggle.setChecked(False)
        self.modeToggle.setToolTip(
            "If checked, the table will be populated with the true wavelength values. Otherwise, it will use the index of the wavelengths."
        )
        self.modeToggle.clicked.connect(self._onModeChanged)

        self.table = QTableWidget(self)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Name", "R", "G", "B"])
        self._setTableDelegates()
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

        self.addButton = QPushButton("Add Band", self)
        self.addButton.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self.deleteButton = QPushButton("Delete Band", self)
        self.deleteButton.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )

        self.buttonLayout = QHBoxLayout()
        self.buttonLayout.addWidget(self.addButton)
        self.buttonLayout.addStretch()  # pushes the buttons apart from each other
        self.buttonLayout.addWidget(self.deleteButton)

        self.bandView = getBandView(self.proj, self.imageIndex, self)

        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.toggleButton)
        self.layout.addLayout(self.buttonLayout)
        self.layout.addWidget(self.modeToggle)
        self.layout.addWidget(self.table)
        self.layout.addWidget(self.bandView)

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
        bands = self.proj.getImage(self.imageIndex).band
        self.table.setRowCount(len(bands))
        self.table.setMinimumHeight(
            self.table.verticalHeader().defaultSectionSize() * (len(bands) + 1)
        )

        wavelengths = self.proj.getImage(self.imageIndex).metadata.wavelengths
        for row, band in enumerate(bands):
            self.table.setItem(row, 0, QTableWidgetItem(band.name))
            if self.useWavelengthValues:
                for col, idx in enumerate([band.r, band.g, band.b], start=1):
                    combo = QComboBox(self.table)
                    combo.addItems([str(w) for w in wavelengths])
                    combo.setCurrentIndex(idx)
                    combo.currentIndexChanged.connect(
                        lambda value, r=row, c=col: self._onComboChanged(r, c, value)
                    )
                    self.table.setCellWidget(row, col, combo)
            else:
                self.table.setItem(row, 1, QTableWidgetItem(str(band.r)))
                self.table.setItem(row, 2, QTableWidgetItem(str(band.g)))
                self.table.setItem(row, 3, QTableWidgetItem(str(band.b)))

        self.disableProjectUpdating = False

    def _onComboChanged(self, row, col, value):
        if self.disableProjectUpdating:
            return
        if col == 1:
            self.proj.updateBand(self.imageIndex, row, r=value)
        elif col == 2:
            self.proj.updateBand(self.imageIndex, row, g=value)
        elif col == 3:
            self.proj.updateBand(self.imageIndex, row, b=value)

    def _setTableDelegates(self):
        if self.useWavelengthValues:
            wavelengths = self.proj.getImage(self.imageIndex).metadata.wavelengths
            self.table.setItemDelegateForColumn(1, None)
            self.table.setItemDelegateForColumn(2, None)
            self.table.setItemDelegateForColumn(3, None)
        else:
            self.table.setItemDelegateForColumn(1, self.IntegerDelegate(self))
            self.table.setItemDelegateForColumn(2, self.IntegerDelegate(self))
            self.table.setItemDelegateForColumn(3, self.IntegerDelegate(self))

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
        """Add a new band configuration to the project."""
        self.proj.addBand(self.imageIndex)
        # the project context will implicitly call _populateTable after updating

    @pyqtSlot()
    def _onDeleteButtonPressed(self):
        """Delete the selected band configuration from the project."""
        selected_items = self.table.selectedItems()
        if selected_items:
            row = selected_items[0].row()
            self.proj.removeBand(self.imageIndex, row)
            # the project context will implicitly call _populateTable after updating

    @pyqtSlot(QTableWidgetItem)
    def _onItemChanged(self, item):
        # ignore project updates if we are currently updating the table, to avoid infinite loop
        if self.disableProjectUpdating:
            return

        row = item.row()
        column = item.column()
        value = item.text()
        if column == 0:
            self.proj.updateBand(self.imageIndex, row, name=item.text())
            return

        metadata = self.proj.getImage(self.imageIndex).metadata
        if self.useWavelengthValues:
            wavelengths = metadata.wavelengths
            idx = int(value)
            clampedValue = idx
        else:
            range_ = len(metadata.wavelengths) - 1
            clampedValue = max(min(int(value), range_), 0)

        if column == 1:
            self.proj.updateBand(self.imageIndex, row, r=clampedValue)
        elif column == 2:
            self.proj.updateBand(self.imageIndex, row, g=clampedValue)
        elif column == 3:
            self.proj.updateBand(self.imageIndex, row, b=clampedValue)

        # If we just updated the currently selected band in the band view, refresh it
        if row == self.bandView.viewModel.bandIndex:
            self.bandView.viewModel.selectBand(row)

    @pyqtSlot()
    def _onRowSelected(self):
        selectedItems = self.table.selectedItems()
        if selectedItems:
            row = selectedItems[0].row()
            logger.info("Band selected: %d", row)
            self.bandView.viewModel.selectBand(row)
            self._emitBandChangedSignal()

    @pyqtSlot(int, ProjectContext.ChangeType)
    def _onProjectDataChanged(self, index, changeType):
        if index == self.imageIndex and changeType == ProjectContext.ChangeType.BAND:
            self._populateTable()
            # emit signal
            self._emitBandChangedSignal()

    @pyqtSlot()
    def _onModeChanged(self):
        self.useWavelengthValues = self.modeToggle.isChecked()
        self._setTableDelegates()
        self._populateTable()

    def _emitBandChangedSignal(self):
        selectedItems = self.table.selectedItems()
        if selectedItems:
            row = selectedItems[0].row()
            self.sigBandChanged.emit(self.proj.getImage(self.imageIndex).band[row])

    class IntegerDelegate(QStyledItemDelegate):
        def createEditor(self, parent, option, index):
            editor = QLineEdit(parent)
            editor.setValidator(QIntValidator())
            return editor

    class WavelengthDelegate(QStyledItemDelegate):
        def __init__(self, parent, wavelengths):
            super().__init__(parent)
            self.wavelengths = wavelengths

        def createEditor(self, parent, option, index):
            combo = QComboBox(parent)
            # Convert all wavelengths to string for display
            combo.addItems([str(w) for w in self.wavelengths])
            return combo

        def setEditorData(self, editor, index):
            idx = int(index.model().data(index, Qt.ItemDataRole.EditRole))
            editor.setCurrentIndex(idx)

        def setModelData(self, editor, model, index):
            selected_idx = editor.currentIndex()
            model.setData(index, selected_idx, Qt.ItemDataRole.EditRole)

        def displayText(self, value, locale):
            # Show the wavelength value if value is a valid index
            idx = int(value)
            return str(self.wavelengths[idx])
