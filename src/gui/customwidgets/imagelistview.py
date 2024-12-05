# standard library

# third party imports
from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtWidgets import QListView
import pyqtgraph as pg

from models.imagedatatype import ImageDataType


# local imports


class ImageListView(QListView):
    def __init__(self, parent=None, model=None):
        super(ImageListView, self).__init__(parent)
        if model:
            print("Model set to: ", model)
            self.setModel(model)

        self.setViewMode(QListView.ViewMode.IconMode)  # Show as icons (grid layout)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setIconSize(QtCore.QSize(64, 64))  # Set icon size
        self.setSpacing(10)  # Add spacing between items
        self.setUniformItemSizes(True)  # Optimize layout performance
        self.delegate = ImageItemDelegate(self)
        self.setItemDelegate(self.delegate)


class ImageItemDelegate(QtWidgets.QStyledItemDelegate):
    iconSize = QtCore.QRect(0, 0, 64, 64)

    def __init__(self, parent=None):
        super().__init__(parent)

    def paint(self, painter, option, index):
        # Get the data from the model
        data = index.data(QtCore.Qt.ItemDataRole.DecorationRole)
        image = index.data(QtCore.Qt.ItemDataRole.UserRole)
        icon = pg.ImageItem(data, levels=image.defaultStretch.values)
        icon.setRect(self.iconSize)

        label = index.data(QtCore.Qt.ItemDataRole.DisplayRole)

        if icon is None:
            return

        # Create a QGraphicsScene and add items
        scene = QtWidgets.QGraphicsScene()
        scene.addItem(icon)

        text = QtWidgets.QGraphicsTextItem(label)
        text.setPos(0, self.iconSize.height())
        scene.addItem(text)
        # Set the painter to the scene
        # scene.render(painter, QtCore.QRectF(option.rect))
        scene.render(painter, QtCore.QRectF(option.rect))
