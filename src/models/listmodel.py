# standard library
import logging

# third party imports
from PyQt6.QtCore import Qt, QModelIndex, QAbstractListModel

# local imports

logger = logging.getLogger(__name__)


class ListModel(QAbstractListModel):
    def __init__(self, data=None, parent=None):
        super().__init__(parent)
        self._data = data if data else []

    def rowCount(self, parent=QModelIndex()):
        """

        Args:
            parent:

        Returns:

        """
        return len(self._data)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None

        if role == Qt.ItemDataRole.DisplayRole:
            return self._data[index.row()]

        return None

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if not index.isValid():
            return False

        category = type(self._data[index.row()])
        if not isinstance(value, category):
            logger.error(f"Value {value} is not of type {type(category)}")
            return False

        if role == Qt.ItemDataRole.EditRole:
            self._data[index.row()] = value
            self.dataChanged.emit(index, index)
            return True

        return False

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsEditable
