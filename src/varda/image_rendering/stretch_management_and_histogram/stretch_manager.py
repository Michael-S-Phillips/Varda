# varda/features/image_view_stretch/stretch_utils.py
# Existing file to be modified

# standard library
import logging

# third party imports
from PyQt6.QtCore import pyqtSlot, Qt, pyqtSignal
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
    QToolButton,
)

# local imports
from varda.project import ProjectContext
from varda.common.entities import Stretch
from varda.image_rendering.stretch_management_and_histogram.histogram_view import (
    getHistogramView,
)
from varda.image_rendering.stretch_management_and_histogram.stretch_preset_generator import (
    StretchPresetSelector,
)

logger = logging.getLogger(__name__)


class StretchManager(QWidget):
    """A widget to display a list of all the stretches associated with an image, and manage them.

    This includes being able to create, delete, and modify stretch configurations.
    Each stretch has a name, and minimum/maximum values for R, G, and B channels.
    """

    sigStretchChanged = pyqtSignal(Stretch)

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
        self.table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
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
        self.stretchPresetSelector = StretchPresetSelector(self)

        self.layout = QVBoxLayout(self)
        self.layout.addWidget(self.toggleButton)
        self.layout.addLayout(self.buttonLayout)
        self.layout.addWidget(self.table)
        self.layout.addWidget(self.stretchPresetSelector)
        self.layout.addWidget(self.histogramView)

        self.setLayout(self.layout)

    def _connectSignals(self):
        self.table.itemSelectionChanged.connect(self._onRowSelected)
        self.table.itemChanged.connect(self._onItemChanged)
        self.toggleButton.clicked.connect(self._toggleTable)
        self.addButton.clicked.connect(self._onAddButtonPressed)
        self.deleteButton.clicked.connect(self._onDeleteButtonPressed)
        self.proj.sigDataChanged.connect(self._onProjectDataChanged)
        self.stretchPresetSelector.sigStretchPresetApplied.connect(
            self._onStretchPresetApplied
        )

    def _populateTable(self):
        self.disableProjectUpdating = True
        stretches = self.proj.getImage(self.imageIndex).stretch
        self.table.setRowCount(len(stretches))
        self.table.setMinimumHeight(
            self.table.verticalHeader().defaultSectionSize() * (len(stretches) + 1)
        )
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

    @pyqtSlot(int)
    def _onStretchPresetApplied(self, preset_id):
        pass

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
            # update histogram's selected stretch
            row = selectedItems[0].row()
            self.histogramView.viewModel.selectStretch(row)
            self._emitStretchChangedSignal()

    @pyqtSlot(int, ProjectContext.ChangeType)
    def _onProjectDataChanged(self, index, changeType):
        # Guard against recursion
        if self._handling_change:
            logger.debug("Prevented recursive call in _onProjectDataChanged")
            return

        if index == self.imageIndex and changeType is ProjectContext.ChangeType.STRETCH:
            self._handling_change = True
            try:
                self._populateTable()
                # emit signal
                self._emitStretchChangedSignal()
            except Exception as e:
                raise e
            finally:
                self._handling_change = False

    def _emitStretchChangedSignal(self):
        selectedItems = self.table.selectedItems()
        if selectedItems:
            row = selectedItems[0].row()
            self.sigStretchChanged.emit(
                self.proj.getImage(self.imageIndex).stretch[row]
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

        def updateEditorGeometry(self, editor, option, index):
            rect = option.rect
            # Expand the width; adjust the factor as needed
            rect.setWidth(rect.width() * 2)
            editor.setGeometry(rect)
