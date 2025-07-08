from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex, QVariant
from PyQt6.QtGui import QColor


class ROITableModel(QAbstractTableModel):
    """Table model exposing ROIs from an ROIManager."""

    HEADERS = ["Index", "Name", "Visible", "Color", "Points", "Spectrum"]

    def __init__(self, roiManager, imageIndex=0, parent=None):
        super().__init__(parent)
        self.roiManager = roiManager
        self.imageIndex = imageIndex

        # reconnect on data changes
        roiManager.sigROIAdded.connect(self._onDataChanged)
        roiManager.sigROIUpdated.connect(self._onDataChanged)
        roiManager.sigROIRemoved.connect(self._onDataChanged)

    def rowCount(self, parent=QModelIndex()):
        return len(self.rois())

    def columnCount(self, parent=QModelIndex()):
        return len(self.HEADERS)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return QVariant()

        roi = self.rois()[index.row()]
        col = index.column()

        # Display data
        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return index.row()
            if col == 1:
                return roi.name
            if col == 2:
                return "Yes" if roi.visible else "No"
            if col == 4:
                return len(roi.points)
            if col == 5:
                return "Yes" if roi.meanSpectrum is not None else "No"
        # Decoration (color swatch)
        if role == Qt.ItemDataRole.DecorationRole and col == 3:
            return roi.color  # assume QColor

        # Edit roles
        if role == Qt.ItemDataRole.EditRole:
            if col == 1:
                return roi.name
            if col == 2:
                return roi.visible

        return QVariant()

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if (
            orientation == Qt.Orientation.Horizontal
            and role == Qt.ItemDataRole.DisplayRole
        ):
            return self.HEADERS[section]
        return super().headerData(section, orientation, role)

    def flags(self, index):
        base = super().flags(index)
        if not index.isValid():
            return base
        if index.column() in (1, 2, 3):  # make Name, Visible, Color editable
            return base | Qt.ItemFlag.ItemIsEditable
        return base

    def setData(self, index, value, role=Qt.ItemDataRole.EditRole):
        if not index.isValid():
            return False
        roi = self.rois()[index.row()]
        col = index.column()

        if col == 1:  # name
            self.roiManager.updateROI(roi.id, name=value)
        elif col == 2:  # visible
            self.roiManager.updateROI(roi.id, visible=bool(value))
        elif col == 3 and isinstance(value, QColor):
            self.roiManager.updateROI(roi.id, color=value)
        else:
            return False

        self.dataChanged.emit(index, index, [role])
        return True

    def rois(self):
        return self.roiManager.getROIsForImage(self.imageIndex)

    def _onDataChanged(self, *args):
        # fully reset view when any change happens
        self.beginResetModel()
        self.endResetModel()
