"""Table view for ROICollection with color delegate."""

import logging

from PyQt6.QtCore import pyqtSignal, Qt, QSize, QEvent, QPoint
from PyQt6.QtGui import QColor, QPen, QBrush, QCursor, QAction
from PyQt6.QtWidgets import (
    QTableView,
    QStyledItemDelegate,
    QColorDialog,
    QMenu,
    QInputDialog,
    QMessageBox,
)

from varda.rois.roi_table_model import ROITableModel

logger = logging.getLogger(__name__)


class ROITableView(QTableView):
    roiSelected = pyqtSignal(int)  # emit fid

    def __init__(self, model: ROITableModel, parent=None):
        super().__init__(parent)
        self._roiModel = model
        self.setModel(model)
        self.setSelectionBehavior(self.SelectionBehavior.SelectRows)
        self.setItemDelegateForColumn(2, ColorDelegate(self))
        self.doubleClicked.connect(self._onDoubleClick)

        header = self.horizontalHeader()
        if header is not None:
            header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            header.customContextMenuRequested.connect(self._onHeaderContextMenu)

    def _onDoubleClick(self, index):
        fid = self._roiModel.fidForRow(index.row())
        if fid is not None:
            self.roiSelected.emit(fid)

    def _onHeaderContextMenu(self, pos: QPoint) -> None:
        header = self.horizontalHeader()
        if header is None:
            return
        section = header.logicalIndexAt(pos)
        columnName = self._roiModel.userColumnAt(section)
        if columnName is None:
            return  # not a user-added column

        menu = QMenu(self)
        renameAction = QAction("Rename Column...", menu)
        deleteAction = QAction("Delete Column", menu)
        renameAction.triggered.connect(lambda: self._renameColumn(columnName))
        deleteAction.triggered.connect(lambda: self._deleteColumn(columnName))
        menu.addAction(renameAction)
        menu.addAction(deleteAction)
        menu.popup(QCursor.pos())

    def _renameColumn(self, columnName: str) -> None:
        newName, ok = QInputDialog.getText(
            self, "Rename Column", "New name:", text=columnName
        )
        if not ok:
            return
        try:
            self._roiModel.collection.renameColumn(columnName, newName)
        except (ValueError, KeyError) as e:
            QMessageBox.warning(self, "Cannot Rename Column", str(e))

    def _deleteColumn(self, columnName: str) -> None:
        reply = QMessageBox.question(
            self,
            "Delete Column",
            f"Delete column '{columnName}' and all of its values?",
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._roiModel.collection.removeColumn(columnName)


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
