from PyQt6.QtCore import pyqtSlot, Qt
from PyQt6.QtGui import QIntValidator
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
    QLayout, QToolButton,
)

from core.data import ProjectContext
from features.image_view_band import getBandView


class BandManager(QWidget):
    """A widget to display a list of all the bands associated with an image, and manage them.

    This includes being able to create, delete, and rename bands.
    """

    def __init__(self, proj: ProjectContext, imageIndex: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Band Manager")
        self.proj = proj
        self.imageIndex = imageIndex
        self._initUI()
        self._connectSignals()
        self._populateTable()

        self.disableProjectUpdating = False

    def _initUI(self):
        self.table = QTableWidget(self)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Name", "R", "G", "B"])
        self.table.setItemDelegateForColumn(1, self.IntegerDelegate(self))
        self.table.setItemDelegateForColumn(2, self.IntegerDelegate(self))
        self.table.setItemDelegateForColumn(3, self.IntegerDelegate(self))
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
        for row, band in enumerate(bands):

            self.table.setItem(row, 0, QTableWidgetItem(band.name))
            self.table.setItem(row, 1, QTableWidgetItem(str(band.r)))
            self.table.setItem(row, 2, QTableWidgetItem(str(band.g)))
            self.table.setItem(row, 3, QTableWidgetItem(str(band.b)))

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
        # if updating name, we can stop here
        if column == 0:
            self.proj.updateBand(self.imageIndex, row, name=item.text())
            return

        # otherwise, we need to convert the value to an int, and clamp it to the range of the image wavelengths
        metadata = self.proj.getImage(self.imageIndex).metadata
        range = len(metadata.wavelengths) - 1

        clampedValue = max(min(int(value), range), 0)
        # make sure that the table item is updated to the clamped value
        # item.setText(str(clampedValue))
        if column == 1:
            self.proj.updateBand(self.imageIndex, row, r=clampedValue)
        elif column == 2:
            self.proj.updateBand(self.imageIndex, row, g=clampedValue)
        elif column == 3:
            self.proj.updateBand(self.imageIndex, row, b=clampedValue)

    @pyqtSlot()
    def _onRowSelected(self):
        selectedItems = self.table.selectedItems()
        if selectedItems:
            row = selectedItems[0].row()
            print("row selected!", row)
            self.bandView.viewModel.selectBand(row)

    @pyqtSlot(int, ProjectContext.ChangeType)
    def _onProjectDataChanged(self, index, changeType):
        if index == self.imageIndex and changeType == ProjectContext.ChangeType.BAND:
            self._populateTable()

    class IntegerDelegate(QStyledItemDelegate):
        def createEditor(self, parent, option, index):
            editor = QLineEdit(parent)
            editor.setValidator(QIntValidator())
            return editor
