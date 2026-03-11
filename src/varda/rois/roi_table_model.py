"""Table model backed by ROICollection."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex, QVariant
from PyQt6.QtGui import QColor

from varda.rois.roi_collection import ROICollection


# Fixed columns shown for every collection
_FIXED_COLUMNS = ["FID", "Name", "Color", "Type"]


class ROITableModel(QAbstractTableModel):
    """Table model exposing ROIs from an ROICollection.

    Fixed columns: FID (read-only), Name (editable), Color (editable via delegate),
    Type (read-only). Additional dynamic columns come from user-added metadata.
    """

    def __init__(self, collection: ROICollection, parent=None) -> None:
        super().__init__(parent)
        self._collection = collection

        collection.sigROIAdded.connect(self._onChanged)
        collection.sigROIRemoved.connect(self._onChanged)
        collection.sigROIUpdated.connect(self._onChanged)

    @property
    def collection(self) -> ROICollection:
        return self._collection

    # --- QAbstractTableModel interface ---

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._collection)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(_FIXED_COLUMNS) + len(self._dynamicColumns())

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return QVariant()

        rois = self._collection.getAllROIs()
        if index.row() >= len(rois):
            return QVariant()
        roi = rois[index.row()]
        col = index.column()

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return roi.fid
            if col == 1:
                return roi.name
            if col == 2:
                return None  # color shown via DecorationRole
            if col == 3:
                return roi.roiType.name
            # Dynamic columns
            dyn_col = self._dynamicColumns()
            if col - len(_FIXED_COLUMNS) < len(dyn_col):
                key = dyn_col[col - len(_FIXED_COLUMNS)]
                return roi.properties.get(key, "")

        if role == Qt.ItemDataRole.DecorationRole and col == 2:
            r, g, b, a = roi.color
            return QColor(r, g, b, a)

        if role == Qt.ItemDataRole.EditRole:
            if col == 1:
                return roi.name

        return QVariant()

    def headerData(self, section: int, orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            all_cols = list(_FIXED_COLUMNS) + self._dynamicColumns()
            if section < len(all_cols):
                return all_cols[section]
        return super().headerData(section, orientation, role)

    def flags(self, index: QModelIndex):
        base = super().flags(index)
        if not index.isValid():
            return base
        col = index.column()
        # Name and Color are editable; dynamic columns are editable
        if col == 1 or col == 2 or col >= len(_FIXED_COLUMNS):
            return base | Qt.ItemFlag.ItemIsEditable
        return base

    def setData(self, index: QModelIndex, value, role: int = Qt.ItemDataRole.EditRole) -> bool:
        if not index.isValid():
            return False

        rois = self._collection.getAllROIs()
        if index.row() >= len(rois):
            return False
        roi = rois[index.row()]
        col = index.column()

        if col == 1:  # Name
            self._collection.updateROI(roi.fid, name=value)
        elif col == 2 and isinstance(value, QColor):  # Color
            color = (value.red(), value.green(), value.blue(), value.alpha())
            self._collection.updateROI(roi.fid, color=color)
        elif col >= len(_FIXED_COLUMNS):
            dyn_col = self._dynamicColumns()
            key = dyn_col[col - len(_FIXED_COLUMNS)]
            self._collection.setProperty(roi.fid, key, value)
        else:
            return False

        self.dataChanged.emit(index, index, [role])
        return True

    def fidForRow(self, row: int) -> int | None:
        """Get the fid for a given row index."""
        rois = self._collection.getAllROIs()
        if row < len(rois):
            return rois[row].fid
        return None

    # --- Internal ---

    def _dynamicColumns(self) -> list[str]:
        """Return names of user-added columns (non-core, non-geometry)."""
        core = {"name", "color", "roi_type", "geometry"}
        return [c for c in self._collection.gdf.columns if c not in core]

    def _onChanged(self, *args) -> None:
        self.beginResetModel()
        self.endResetModel()
