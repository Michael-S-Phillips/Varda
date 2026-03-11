"""Table view for ROICollection with color delegate."""

import logging

from PyQt6.QtCore import pyqtSignal, Qt, QSize, QEvent
from PyQt6.QtGui import QColor, QPen, QBrush
from PyQt6.QtWidgets import QTableView, QStyledItemDelegate, QColorDialog

from varda.rois.roi_table_model import ROITableModel

logger = logging.getLogger(__name__)


class ROITableView(QTableView):
    roiSelected = pyqtSignal(int)  # emit fid

    def __init__(self, model: ROITableModel, parent=None):
        super().__init__(parent)
        self.setModel(model)
        self.setSelectionBehavior(self.SelectionBehavior.SelectRows)
        self.setItemDelegateForColumn(2, ColorDelegate(self))
        self.doubleClicked.connect(self._onDoubleClick)

    def _onDoubleClick(self, index):
        fid = self.model().fidForRow(index.row())
        if fid is not None:
            self.roiSelected.emit(fid)


class ColorDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        return None

    def editorEvent(self, event, model, option, index):
        if event.type() == QEvent.Type.MouseButtonDblClick:
            currentColor = index.data(Qt.ItemDataRole.DecorationRole)
            if not isinstance(currentColor, QColor):
                currentColor = QColor(255, 0, 0, 128)
            newColor = QColorDialog.getColor(initial=currentColor, parent=option.widget)
            if newColor.isValid():
                model.setData(index, newColor, Qt.ItemDataRole.EditRole)
            return True
        return super().editorEvent(event, model, option, index)

    def paint(self, painter, option, index):
        super().paint(painter, option, index)

        color = index.data(Qt.ItemDataRole.DecorationRole)
        if not isinstance(color, QColor):
            return

        c = QColor(color)
        c.setAlpha(255)

        r = option.rect.adjusted(4, 4, -4, -4)

        painter.save()
        painter.setPen(QPen(Qt.GlobalColor.black, 1))
        painter.setBrush(QBrush(c))
        painter.drawRect(r)
        painter.restore()

    def sizeHint(self, option, index):
        base = super().sizeHint(option, index)
        return QSize(base.width(), max(base.height(), 24))
