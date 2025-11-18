# standard library

# third party imports
from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtWidgets import QListView, QListWidget, QListWidgetItem
from PyQt6.QtCore import Qt

# local imports
from varda.common import ObservableList
from varda.image_rendering.image_renderer import ImageRenderer
from varda.image_rendering.raster_view import VardaImageItem

ICON_SIZE = 64


class ImageListWidget(QListWidget):
    """Widget for displaying all the images of a project.

    This class gives users a way to see previews of all the images in the project.
    Users can also select images, which other classes can use to provide context
    actions based on which image is selected.
    """

    def __init__(self, imageList: ObservableList, parent=None):
        super().__init__(parent)
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setIconSize(QtCore.QSize(64, 64))  # Set icon size
        self.imageList = imageList

        self.setItemDelegate(ImageItemDelegate(self))

        self._updateItems()
        self.imageList.sigDataChanged.connect(self._updateItems)

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

        # Apply darkening effect if the item is selected
        if option.state & QtWidgets.QStyle.StateFlag.State_Selected:
            imageRect = QtCore.QRect(option.rect.topLeft(), self.iconSize.size())
            painter.fillRect(imageRect, QtGui.QColor(0, 0, 0, 60))

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
