# standard library

# third party imports
from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtWidgets import QListView, QListWidget, QListWidgetItem
from PyQt6.QtCore import Qt
import pyqtgraph as pg


# local imports
from core.data import ProjectContext
from core.entities import Image


class ImageViewList(QListView):

    sigOpenRasterView = QtCore.pyqtSignal(Image)
    sigOpenStretchView = QtCore.pyqtSignal(Image)
    sigOpenBandView = QtCore.pyqtSignal(Image)

    def __init__(self, parent=None, viewmodel=None):
        super().__init__(parent)
        if viewmodel:
            self.setModel(viewmodel)

        self.setViewMode(QListView.ViewMode.IconMode)  # Show as icons (grid layout)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setIconSize(QtCore.QSize(256, 256))  # Set icon size
        self.setSpacing(10)  # Add spacing between items
        self.setUniformItemSizes(True)  # Optimize layout performance
        self.delegate = ImageItemDelegate(self)
        self.setItemDelegate(self.delegate)

    # def contextMenuEvent(self, event):
    #     # Check if the right click happened on an item
    #     index = self.indexAt(event.pos())
    #     if index.isValid():
    #         contextMenu = self.createContextMenu(index)
    #         contextMenu.exec(event.globalPos())
    #     else:
    #         print("No item selected")
    #
    # def createContextMenu(self, index):
    #     indexVal = index.row() + index.column()
    #     contextMenu = QtWidgets.QMenu(self)
    #     openView = contextMenu.addMenu("Open View")
    #     rasterView = openView.addAction("RasterData View")
    #     bandView = openView.addAction("Band View")
    #     stretchView = openView.addAction("Stretch View")
    #     rasterView.triggered.connect(lambda: self.sigOpenRasterView.emit(indexVal))
    #     bandView.triggered.connect(lambda: self.sigOpenBandView.emit(indexVal))
    #     stretchView.triggered.connect(lambda: self.sigOpenStretchView.emit(indexVal))
    #     return contextMenu


class ImageListWidget(QListWidget):
    def __init__(self, proj: ProjectContext, parent=None):
        super().__init__(parent)
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setIconSize(QtCore.QSize(64, 64))  # Set icon size
        self.proj = proj

        delegate = ImageItemDelegate(self)
        self.setItemDelegate(delegate)

        self.updateItems()
        self.proj.sigDataChanged.connect(self.updateItems)

    def updateItems(self):
        self.clear()
        for image in self.proj.getAllImages():
            item = QListWidgetItem()
            item.setText("Image")
            item.setData(Qt.ItemDataRole.UserRole, image)
            pixmap = QPixmap(64, 64)
            pixmap.fill(Qt.GlobalColor.blue)  # Example placeholder image
            item.setIcon(QIcon(pixmap))
            self.addItem(item)
        self.update()

    # def createContextMenu(self, index):
    #     contextMenu = QtWidgets.QMenu(self)
    #     openView = contextMenu.addMenu("Open View")
    #     rasterView = openView.addAction("RasterData View")
    #     bandView = openView.addAction("Band View")
    #     stretchView = openView.addAction("Stretch View")
    #     image = index.data(QtCore.Qt.ItemDataRole.UserRole)
    #     rasterView.triggered.connect(lambda: self.sigOpenRasterView.emit(image))
    #     bandView.triggered.connect(lambda: self.sigOpenBandView.emit(image))
    #     stretchView.triggered.connect(lambda: self.sigOpenStretchView.emit(image))
    #     return contextMenu


class ImageItemDelegate(QtWidgets.QStyledItemDelegate):
    """Delegate that allows for custom rendering of list items. This is used so we
    can use the Image entity data to display a preview."""

    iconSize = QtCore.QRect(0, 0, 64, 64)

    def __init__(self, parent=None):
        super().__init__(parent)

    def paint(self, painter, option, index):
        # Get the data from the model

        image = index.data(QtCore.Qt.ItemDataRole.UserRole)
        # for now use the first band
        data = image.raster[:, :, [image.band[0].r, image.band[0].g, image.band[0].b]]
        icon = pg.ImageItem(data, levels=image.stretch[0].toList())
        icon.setRect(self.iconSize)
        label = index.data(QtCore.Qt.ItemDataRole.DisplayRole)

        if icon is None:
            return

        # Create a QGraphicsScene and add items
        scene = QtWidgets.QGraphicsScene()
        scene.addItem(icon)

        text = QtWidgets.QGraphicsTextItem(label)
        text.setFont(QtGui.QFont(text.font().family(), 16))
        text.setPos(0, self.iconSize.height())
        scene.addItem(text)
        # Set the painter to the scene
        # scene.render(painter, QtCore.QRectF(option.rect))
        scene.render(painter, QtCore.QRectF(option.rect))

        # Apply darkening effect if the item is selected
        if option.state & QtWidgets.QStyle.StateFlag.State_Selected:
            imageRect = QtCore.QRect(option.rect.topLeft(), self.iconSize.size())
            painter.fillRect(imageRect, QtGui.QColor(0, 0, 0, 60))
