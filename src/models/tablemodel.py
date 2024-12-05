# standard library
import logging

# third party imports
from PyQt6.QtCore import Qt, QModelIndex, QAbstractTableModel

# local imports

logger = logging.getLogger(__name__)


class TableModel(QAbstractTableModel):
    def __init__(self, headerHorizontal=None, data=None, parent=None):
        super().__init__(parent)

        self._headerHorizontal = headerHorizontal if headerHorizontal else []
        self._headerVertical = [key for key in (data.keys() if data else [])]
        self._data = [value for value in (data.values() if data else [])]

    def rowCount(self, parent=QModelIndex()):
        return len(self._data) if self._data else 0

    def columnCount(self, parent=QModelIndex()):
        return len(self._data[0]) if self._data else 0

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        if role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.EditRole:
            return self._data[index.row()][index.column()]

        return None

    def getRow(self, index):
        return self._data[index.row()]

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role == Qt.ItemDataRole.DisplayRole:
            if orientation == Qt.Orientation.Horizontal:
                return self._headerHorizontal[section]
            elif orientation == Qt.Orientation.Vertical:
                return self._headerVertical[section]
        return None

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if not index.isValid():
            return False
        category = type(self._data[index.row()][index.column()])
        if not isinstance(value, category):
            logger.error(f"Value {value} is not of type {type(category)}")
            return False

        if role == Qt.ItemDataRole.EditRole:
            self._data[index.row()][index.column()] = value
            self.dataChanged.emit(index, index)
            return True

        return False

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsEditable
