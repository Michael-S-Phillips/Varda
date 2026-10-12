"""The endmember table: one row per endmember class, the active row is where
lasso selections go."""

from __future__ import annotations

import json
from collections.abc import Sequence

import numpy as np
from PyQt6.QtCore import QSignalBlocker, Qt, pyqtSignal
from PyQt6.QtGui import QBrush, QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QColorDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from varda.workspaces.spectral_hourglass.hourglass_model import HourglassModel

_COLUMNS = ["", "Name", "Pixels", "Identified as"]


class EndmemberTable(QWidget):
    sigActiveChanged = pyqtSignal(object)  # endmember id or None

    def __init__(self, model: HourglassModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.model = model
        self._activeId: int | None = None

        self.table = QTableWidget(0, len(_COLUMNS))
        self.table.setHorizontalHeaderLabels(_COLUMNS)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        vertical, header = self.table.verticalHeader(), self.table.horizontalHeader()
        assert vertical is not None and header is not None
        vertical.setVisible(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(0, 24)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.itemChanged.connect(self._onItemChanged)
        self.table.cellDoubleClicked.connect(self._onCellDoubleClicked)
        self.table.currentCellChanged.connect(lambda row, *_: self._onCurrentRow(row))

        self.addButton = QPushButton("New")
        self.addButton.setToolTip("Add an empty endmember and make it the lasso target")
        self.addButton.clicked.connect(self._addEndmember)
        self.mergeButton = QPushButton("Merge")
        self.mergeButton.setToolTip("Merge the selected endmembers into the first")
        self.mergeButton.clicked.connect(self._mergeSelected)
        self.deleteButton = QPushButton("Delete")
        self.deleteButton.clicked.connect(self._deleteSelected)
        self.suggestCount = QSpinBox()
        self.suggestCount.setRange(2, 30)
        self.suggestCount.setValue(5)
        self.suggestCount.setToolTip("How many groups to suggest")
        self.suggestButton = QPushButton("Suggest")
        self.suggestButton.setToolTip(
            "Group the candidate pure pixels into new endmembers by k-means; "
            "then refine them in the n-D view"
        )
        self.suggestButton.clicked.connect(self._suggest)
        saveButton = QPushButton("Save…")
        saveButton.setToolTip(
            "Save the endmember classes (names, colours, pixels) as JSON"
        )
        saveButton.clicked.connect(self._save)
        loadButton = QPushButton("Load…")
        loadButton.clicked.connect(self._load)
        exportButton = QPushButton("Export Spectra…")
        exportButton.setToolTip("Write the endmember mean spectra as a CSV library")
        exportButton.clicked.connect(self._exportSpectra)

        edit = QHBoxLayout()
        for button in (self.addButton, self.mergeButton, self.deleteButton):
            edit.addWidget(button)
        edit.addStretch()
        edit.addWidget(QLabel("Suggest"))
        edit.addWidget(self.suggestCount)
        edit.addWidget(self.suggestButton)
        files = QHBoxLayout()
        files.addStretch()
        for button in (saveButton, loadButton, exportButton):
            files.addWidget(button)

        layout = QVBoxLayout(self)
        layout.addLayout(edit)
        layout.addWidget(self.table)
        layout.addLayout(files)

        model.sigEndmembersChanged.connect(self.refresh)
        self.refresh()

    # --- rows ---------------------------------------------------------------------

    def refresh(self) -> None:
        endmembers = self.model.endmembers
        with QSignalBlocker(self.table):
            self.table.setRowCount(len(endmembers))
            for row, endmember in enumerate(endmembers):
                swatch = QTableWidgetItem()
                swatch.setBackground(QBrush(QColor(endmember.color)))
                swatch.setFlags(
                    Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                )
                swatch.setToolTip("Double-click to change the colour")
                name = QTableWidgetItem(endmember.name)
                count = QTableWidgetItem(str(endmember.pixels.size))
                count.setFlags(count.flags() & ~Qt.ItemFlag.ItemIsEditable)
                count.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                ident = QTableWidgetItem(endmember.identification)
                ident.setFlags(ident.flags() & ~Qt.ItemFlag.ItemIsEditable)
                for column, item in enumerate((swatch, name, count, ident)):
                    item.setData(Qt.ItemDataRole.UserRole, endmember.id)
                    self.table.setItem(row, column, item)
            ids = [e.id for e in endmembers]
            if self._activeId in ids:
                self.table.setCurrentCell(ids.index(self._activeId), 1)
        if self._activeId not in [e.id for e in endmembers]:
            self._setActive(endmembers[-1].id if endmembers else None)

    def _rowId(self, row: int) -> int | None:
        item = self.table.item(row, 1)
        return None if item is None else int(item.data(Qt.ItemDataRole.UserRole))

    def activeEndmemberId(self) -> int | None:
        return self._activeId

    def setActiveEndmember(self, endmemberId: int | None) -> None:
        self._setActive(endmemberId)
        ids = [e.id for e in self.model.endmembers]
        if endmemberId in ids:
            with QSignalBlocker(self.table):
                self.table.setCurrentCell(ids.index(endmemberId), 1)

    def _setActive(self, endmemberId: int | None) -> None:
        if endmemberId != self._activeId:
            self._activeId = endmemberId
            self.sigActiveChanged.emit(endmemberId)

    def _onCurrentRow(self, row: int) -> None:
        if row >= 0:
            self._setActive(self._rowId(row))

    def selectRows(self, rows: Sequence[int]) -> None:
        self.table.clearSelection()
        mode = self.table.selectionMode()
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        for row in rows:
            self.table.selectRow(row)
        self.table.setSelectionMode(mode)

    def _selectedIds(self) -> list[int]:
        rows = sorted({index.row() for index in self.table.selectedIndexes()})
        ids = [self._rowId(r) for r in rows]
        return [i for i in ids if i is not None]

    # --- edits ----------------------------------------------------------------------

    def _onItemChanged(self, item: QTableWidgetItem) -> None:
        if item.column() == 1:
            self.model.renameEndmember(
                int(item.data(Qt.ItemDataRole.UserRole)), item.text()
            )

    def _onCellDoubleClicked(self, row: int, column: int) -> None:
        endmemberId = self._rowId(row)
        if column != 0 or endmemberId is None:
            return
        color = QColorDialog.getColor(
            QColor(self.model.endmember(endmemberId).color), self
        )
        if color.isValid():
            self.model.recolorEndmember(endmemberId, color.name())

    def _addEndmember(self) -> None:
        endmember = self.model.addEndmember()
        self.setActiveEndmember(endmember.id)

    def _mergeSelected(self) -> None:
        ids = self._selectedIds()
        if len(ids) >= 2:
            self.setActiveEndmember(self.model.mergeEndmembers(ids).id)

    def _deleteSelected(self) -> None:
        for endmemberId in self._selectedIds():
            self.model.removeEndmember(endmemberId)

    def _suggest(self) -> None:
        try:
            created = self.model.suggestEndmembers(self.suggestCount.value())
        except ValueError as error:
            QMessageBox.information(self, "Suggest endmembers", str(error))
            return
        if created:
            self.setActiveEndmember(created[0].id)

    # --- files ------------------------------------------------------------------------

    def _save(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Endmembers",
            f"{self.model.image.name}_endmembers.json",
            "JSON (*.json)",
        )
        if path:
            with open(path, "w") as f:
                json.dump(self.model.endmembersToJson(), f, indent=1)

    def _load(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Load Endmembers", "", "JSON (*.json)"
        )
        if not path:
            return
        try:
            with open(path) as f:
                self.model.endmembersFromJson(json.load(f))
        except (OSError, ValueError, KeyError) as error:
            QMessageBox.warning(
                self, "Load Endmembers", f"Could not load {path}:\n{error}"
            )

    def _exportSpectra(self) -> None:
        endmembers = self.model.usableEndmembers()
        if not endmembers or self.model.prepared is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Endmember Spectra",
            f"{self.model.image.name}_endmembers.csv",
            "CSV (*.csv)",
        )
        if not path:
            return
        wavelengths = self.model.wavelengths
        x = (
            wavelengths
            if wavelengths is not None
            else np.arange(self.model.cube.shape[2]) + 1
        )
        spectra = [self.model.endmemberSpectrum(e.id) for e in endmembers]
        header = ",".join(
            ["wavelength", *[e.name.replace(",", " ") for e in endmembers]]
        )
        np.savetxt(
            path,
            np.column_stack([x, *spectra]),
            delimiter=",",
            header=header,
            comments="",
        )
