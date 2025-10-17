# standard library
import os

# third party imports
from PyQt6 import QtWidgets, QtCore, QtGui
from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtWidgets import QListView, QListWidget, QListWidgetItem
from PyQt6.QtCore import Qt
import pyqtgraph as pg


# local imports
from varda.project import ProjectContext


class ImageListWidget(QListWidget):
    """Widget for displaying all the images of a project.

    This class gives users a way to see previews of all the images in the project.
    Users can also select images, which other classes can use to provide context
    actions based on which image is selected.
    """

    def __init__(self, proj: ProjectContext, parent=None):
        super().__init__(parent)
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setIconSize(QtCore.QSize(64, 64))  # Set icon size
        self.proj = proj

        delegate = ImageItemDelegate(self)
        self.setItemDelegate(delegate)

        self._updateItems()
        self.proj.sigDataChanged.connect(self._updateItems)

        # Also listen for stretch changes to refresh thumbnails
        self.proj.sigDataChanged.connect(self._on_data_changed)

    def _on_data_changed(self, index, change_type):
        """Handle project data changes to refresh thumbnails when stretch/band changes"""
        try:
            from varda.project import ProjectContext

            if change_type in [
                ProjectContext.ChangeType.STRETCH,
                ProjectContext.ChangeType.BAND,
            ]:
                # Force a repaint of the specific item or all items
                self.update()  # This will trigger a repaint of all visible items
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Error handling data change in image list: {e}")

    def _updateItems(self):
        self.clear()
        for image in self.proj.getAllImages():
            item = QListWidgetItem()

            # Prioritize metadata.name for processed images, fallback to filename
            if image.metadata.name:
                # Use the metadata name (which includes processed names like "image_b1_b2_b3_DCS")
                display_name = image.metadata.name
            else:
                # Fallback to filename for images without custom names
                file_path = image.metadata.filePath
                if file_path:
                    base_name = os.path.basename(file_path)
                    display_name = os.path.splitext(base_name)[0]
                else:
                    # Final fallback to driver
                    display_name = image.metadata.driver

            item.setText(display_name)
            item.setData(Qt.ItemDataRole.UserRole, image)
            pixmap = QPixmap(64, 64)
            pixmap.fill(QtGui.QColor("blue"))  # Example placeholder image
            item.setIcon(QIcon(pixmap))
            self.addItem(item)
        self.update()


class ImageItemDelegate(QtWidgets.QStyledItemDelegate):
    """Delegate that allows for custom rendering of list items. This is used so we
    can use the Image entity data to display a preview."""

    iconSize = QtCore.QRect(0, 0, 64, 64)

    def __init__(self, parent=None):
        super().__init__(parent)

    def paint(self, painter, option, index):
        """Renders an Image."""

        # Get the data from the model
        image = index.data(QtCore.Qt.ItemDataRole.UserRole)

        # Get the current stretch index from the main view
        current_stretch_index = self._get_current_stretch_index(image.index)

        # Use the current band configuration
        current_band = image.band[0]  # For now, use the first band

        # Extract RGB data based on current band
        data = image.raster[:, :, [current_band.r, current_band.g, current_band.b]]

        # Use the current stretch instead of always stretch[0]
        stretch_levels = image.stretch[current_stretch_index].toList()
        icon = pg.ImageItem(data, levels=stretch_levels)

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
