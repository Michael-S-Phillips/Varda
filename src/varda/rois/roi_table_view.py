import logging

from PyQt6.QtCore import pyqtSignal, Qt, QSize
from PyQt6.QtGui import QColor, QPen, QBrush
from PyQt6.QtWidgets import QTableView, QStyledItemDelegate, QColorDialog

from varda.rois.roi_table_model import ROITableModel

logger = logging.getLogger(__name__)


class ROITableView(QTableView):
    roiDoubleClicked = pyqtSignal(str)  # emit ROI id

    def __init__(self, model: ROITableModel, parent=None):
        super().__init__(parent)
        self.setModel(model)
        self.setSelectionBehavior(self.SelectionBehavior.SelectRows)
        self.setItemDelegateForColumn(3, ColorDelegate(self))
        self.doubleClicked.connect(self._onDoubleClick)

    def _onDoubleClick(self, index):
        roi = self.model()._rois()[index.row()]
        logger.debug(f"ROI {roi.id} double clicked")
        self.roiDoubleClicked.emit(roi.id)


class ColorDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        return None  # we open dialog in setEditorData

    def setEditorData(self, editor, index):
        color = index.data(Qt.ItemDataRole.DecorationRole)
        newColor = QColorDialog.getColor(initial=color, parent=editor)
        if newColor.isValid():
            index.model().setData(index, newColor, Qt.ItemDataRole.EditRole)

    def paint(self, painter, option, index):
        # draw the normal background (for selection, hover, etc.)
        super().paint(painter, option, index)

        # fetch the QColor from the model’s DecorationRole
        color = index.data(Qt.ItemDataRole.DecorationRole)
        if not isinstance(color, QColor):
            return

        # make it fully opaque
        c = QColor(color)
        c.setAlpha(255)

        # compute a slightly inset rect
        r = option.rect.adjusted(4, 4, -4, -4)

        painter.save()
        painter.setPen(QPen(Qt.GlobalColor.black, 1))
        painter.setBrush(QBrush(c))
        painter.drawRect(r)
        painter.restore()

    def sizeHint(self, option, index):
        # give a little extra height so the swatch isn't squashed
        base = super().sizeHint(option, index)
        return QSize(base.width(), max(base.height(), 24))
