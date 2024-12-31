# standard library

# third party imports
from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtWidgets import QListView
import pyqtgraph as pg

from core.entities.image import ImageModel

# local imports


class ImageViewList(QListView):

    sigOpenRasterView = QtCore.pyqtSignal(ImageModel)
    sigOpenStretchView = QtCore.pyqtSignal(ImageModel)
    sigOpenBandView = QtCore.pyqtSignal(ImageModel)

    def __init__(self, parent=None, viewmodel=None):
        super().__init__(parent)
        if viewmodel:
            self.setModel(viewmodel)

        self.setViewMode(QListView.ViewMode.IconMode)  # Show as icons (grid layout)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setIconSize(QtCore.QSize(64, 64))  # Set icon size
        self.setSpacing(10)  # Add spacing between items
        self.setUniformItemSizes(True)  # Optimize layout performance
        self.delegate = ImageItemDelegate(self)
        self.setItemDelegate(self.delegate)

    def contextMenuEvent(self, event):
        # Check if the right click happened on an item
        index = self.indexAt(event.pos())
        if index.isValid():
            contextMenu = self.createContextMenu(index)
            contextMenu.exec(event.globalPos())
        else:
            print("No item selected")

    def createContextMenu(self, index):
        contextMenu = QtWidgets.QMenu(self)
        openView = contextMenu.addMenu("Open View")
        rasterView = openView.addAction("RasterData View")
        bandView = openView.addAction("Band View")
        stretchView = openView.addAction("Stretch View")
        imageModel = index.data(QtCore.Qt.ItemDataRole.UserRole)
        rasterView.triggered.connect(lambda: self.sigOpenRasterView.emit(imageModel))
        bandView.triggered.connect(lambda: self.sigOpenBandView.emit(imageModel))
        stretchView.triggered.connect(lambda: self.sigOpenStretchView.emit(imageModel))
        return contextMenu


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

        # Apply darkening effect if the item is selected
        if option.state & QtWidgets.QStyle.StateFlag.State_Selected:
            imageRect = QtCore.QRect(option.rect.topLeft(), self.iconSize.size())
            painter.fillRect(imageRect, QtGui.QColor(0, 0, 0, 60))
