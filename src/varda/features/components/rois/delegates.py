from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QStyledItemDelegate, QColorDialog


class ColorDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        return None  # we open dialog in setEditorData

    def setEditorData(self, editor, index):
        color = index.data(Qt.ItemDataRole.DecorationRole)
        newColor = QColorDialog.getColor(initial=color, parent=editor)
        if newColor.isValid():
            index.model().setData(index, newColor, Qt.ItemDataRole.EditRole)
