# standard library

# third party imports
from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QListView,
    QListWidget,
    QListWidgetItem,
)
from PyQt6.QtCore import QPoint, Qt, pyqtSignal

# local imports
from varda.common import ObservableList
from varda.image_rendering.image_renderer import ImageRenderer
from varda.image_rendering.raster_view import VardaImageItem

ICON_SIZE = 64


class ImageListWidget(QListWidget):
    """Widget for displaying all the images of a project.

    This class gives users a way to see previews of all the images in the project.
    Interactions are surfaced as signals carrying the affected images, so this
    widget stays independent of what "opening" an image means:

    - ``sigImagesActivated(list[VardaRaster])`` on double-click.
    - ``sigContextMenuRequested(list[VardaRaster], QPoint)`` on right-click over an
      item; the clicked image comes first, followed by any other selected images.
    """

    sigImagesActivated = pyqtSignal(list)
    sigContextMenuRequested = pyqtSignal(list, QPoint)

    def __init__(self, imageList: ObservableList, parent=None):
        super().__init__(parent)
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setIconSize(QtCore.QSize(64, 64))  # Set icon size
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.setMouseTracking(True)  # hover state for the item delegate
        self.imageList = imageList

        self.setItemDelegate(ImageItemDelegate(self))

        self._updateItems()
        self.imageList.sigDataChanged.connect(self._updateItems)
        self.itemDoubleClicked.connect(self._onItemDoubleClicked)
        self.customContextMenuRequested.connect(self._onContextMenuRequested)

    def _onItemDoubleClicked(self, item: QListWidgetItem) -> None:
        self.sigImagesActivated.emit([item.data(Qt.ItemDataRole.UserRole)])

    def _onContextMenuRequested(self, pos: QPoint) -> None:
        clicked = self.itemAt(pos)
        if clicked is None:
            return
        others = [
            item for item in self.selectedItems() if self.row(item) != self.row(clicked)
        ]
        images = [item.data(Qt.ItemDataRole.UserRole) for item in [clicked, *others]]
        self.sigContextMenuRequested.emit(images, self.viewport().mapToGlobal(pos))

    def _updateItems(self):
        self.clear()
        for image in self.imageList:
            item = QListWidgetItem()
            item.setText(image.metadata.name)
            item.setData(Qt.ItemDataRole.UserRole, image)
            pixmap = QPixmap(ICON_SIZE, ICON_SIZE)
            pixmap.fill(QtGui.QColor("pink"))  # default color if image doesnt render
            item.setIcon(QIcon(pixmap))
            self.addItem(item)
        self.update()


class ImageItemDelegate(QtWidgets.QStyledItemDelegate):
    """Delegate that allows for custom rendering of list items. This is used so we
    can use the Image entity data to display a preview."""

    iconSize = QtCore.QRect(0, 0, ICON_SIZE, ICON_SIZE)

    def __init__(self, parent=None):
        super().__init__(parent)

    def paint(self, painter, option, index):
        """Renders an Image."""

        # Get the data from the model
        image = index.data(QtCore.Qt.ItemDataRole.UserRole)
        renderer = ImageRenderer(image)

        # Get the current stretch index from the main view
        icon = VardaImageItem(renderer)
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
        scene.render(painter, QtCore.QRectF(option.rect))

        # Selection: a translucent tint plus a solid frame in the palette's
        # highlight colour over the whole item (thumbnail and label), so it
        # reads at a glance. Hover: a thin frame as a clickability cue.
        highlight = option.palette.highlight().color()
        frame = option.rect.adjusted(1, 1, -2, -2)
        painter.save()
        if option.state & QtWidgets.QStyle.StateFlag.State_Selected:
            tint = QtGui.QColor(highlight)
            tint.setAlpha(60)
            painter.setBrush(tint)
            painter.setPen(QtGui.QPen(highlight, 3))
            painter.drawRoundedRect(frame, 3, 3)
        elif option.state & QtWidgets.QStyle.StateFlag.State_MouseOver:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QtGui.QPen(highlight, 1))
            painter.drawRoundedRect(frame, 3, 3)
        painter.restore()

    def _get_current_stretch_index(self, image_index):
        """Get the current stretch index for an image from the main view"""
        try:
            # Get the main GUI by walking up the parent hierarchy
            parent = self.parent()
            while parent:
                if hasattr(parent, "rasterViews") and hasattr(parent, "proj"):
                    # Found MainGUI
                    main_gui = parent
                    if image_index in main_gui.rasterViews:
                        raster_view = main_gui.rasterViews[image_index]
                        if hasattr(raster_view, "viewModel") and hasattr(
                            raster_view.viewModel, "stretchIndex"
                        ):
                            return raster_view.viewModel.stretchIndex
                    break
                parent = parent.parent()
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(
                f"Error getting current stretch index for image {image_index}: {e}"
            )

        # Fallback to stretch index 0 if we can't find the current one
        return 0
