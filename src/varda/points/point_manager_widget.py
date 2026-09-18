"""Points Manager: a table of the saved pixel points with delete and export."""

from __future__ import annotations

import logging

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QMessageBox,
    QTableView,
    QWidget,
)

from varda.common.ui import ButtonBuilder, HBoxBuilder, VBoxBuilder
from varda.points.point_collection import EXPORT_FILE_FILTER, PointCollection

logger = logging.getLogger(__name__)

_COLUMNS = ("Name", "Image", "X", "Y", "Geo X", "Geo Y")


class PointTableModel(QAbstractTableModel):
    def __init__(self, collection: PointCollection, parent=None) -> None:
        super().__init__(parent)
        self._collection = collection
        self._rows = collection.getAllPoints()
        collection.sigCollectionChanged.connect(self._reload)

    def _reload(self) -> None:
        self.beginResetModel()
        self._rows = self._collection.getAllPoints()
        self.endResetModel()

    def fidAt(self, row: int) -> int:
        return self._rows[row].fid

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(_COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if (
            role == Qt.ItemDataRole.DisplayRole
            and orientation == Qt.Orientation.Horizontal
        ):
            return _COLUMNS[section]
        return None

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        point = self._rows[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return (
                point.name,
                point.image,
                str(point.x),
                str(point.y),
                f"{point.geometry.x:.6f}",
                f"{point.geometry.y:.6f}",
            )[index.column()]
        if role == Qt.ItemDataRole.DecorationRole and index.column() == 0:
            return point.color.toQColor()
        return None


class PointManagerWidget(QWidget):
    sigSelectionChanged = pyqtSignal(object)  # fid (int) or None

    def __init__(self, collection: PointCollection, parent: QWidget | None = None):
        super().__init__(parent)
        self._collection = collection
        self.model = PointTableModel(collection, parent=self)
        self.table = QTableView(self)
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        header = self.table.horizontalHeader()
        if header is not None:
            header.setStretchLastSection(True)
        self.deleteButton = ButtonBuilder("Delete Selected").onClick(
            self._deleteSelected
        )
        self.exportButton = ButtonBuilder("Export…").onClick(self._export)
        self.setLayout(
            VBoxBuilder()
            .withLayout(
                HBoxBuilder()
                .withWidget(self.deleteButton)
                .withWidget(self.exportButton)
                .withStretch()
            )
            .withWidget(self.table)
        )
        selectionModel = self.table.selectionModel()
        if selectionModel is not None:
            selectionModel.selectionChanged.connect(
                lambda *_: self.sigSelectionChanged.emit(self.selectedFid())
            )

    def selectedFid(self) -> int | None:
        selectionModel = self.table.selectionModel()
        rows = selectionModel.selectedRows() if selectionModel is not None else []
        return self.model.fidAt(rows[0].row()) if rows else None

    def _deleteSelected(self) -> None:
        fid = self.selectedFid()
        if fid is not None:
            self._collection.removePoint(fid)

    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export points", "points.geojson", EXPORT_FILE_FILTER
        )
        if not path:
            return
        try:
            written = self._collection.toFile(path)
        except (ValueError, OSError) as error:
            QMessageBox.critical(self, "Export failed", str(error))
            return
        logger.info("Points exported to %s", written)
