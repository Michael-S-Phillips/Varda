"""
This module contains the `ImageManager` class, which manages a collection of images.
It provides methods to add, remove, and link images, and integrates with Qt's model/view framework.

Classes:
    ImageManager: Manages a collection of `ImageModel` instances.
"""

# standard library
import logging
import os

# third-party imports
from PyQt6 import QtCore
from PyQt6.QtCore import Qt

# local imports
from core.data import ProjectContext


logger = logging.getLogger(__name__)


# pylint: disable=unused-argument
class ImageListViewModel(QtCore.QAbstractListModel):
    """A super basic implementation of the

    Attributes:
        _images (list): List of ImageModel instances managed by this class.

    Methods:
        rowCount(parent=QModelIndex()):
            Returns the number of images managed by this class.

        index(row, column=0, parent=QModelIndex()):
            Returns the index of the image at the specified row and column.

        data(index, role=Qt.ItemDataRole.DisplayRole):
            Returns the data for the specified role and index.

        appendImage(imageModel):
            Appends a new ImageModel to the manager.

        removeImage(row):
            Removes the image at the specified row.
    """

    def __init__(self, proj: ProjectContext, parent=None):
        super().__init__(parent)
        self._images = []
        for image in proj.getAllImages():
            self._appendImage(image)

    def rowCount(self, parent=QtCore.QModelIndex()):
        """Get the number of rows in the model."""
        return len(self._images)

    def index(self, row, column=0, parent=QtCore.QModelIndex()):
        """Returns the index of the image at the specified row and column.
        Note that column isn't used. but it's required by the method signature
        """
        return self.createIndex(row, column, self._images[row])

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        """Returns the data for the specified role and index.

        Args:
            index (QModelIndex): Index of the item.
            role (Qt.ItemDataRole): Role for which data is requested.
                role options are defined in ImageDataType.
                 - DisplayRole: Text representation of the item for display. (str)
                 - UserRole: The entire image instance (ImageModel)
                 - DecorationRole: image preview data (subset of raster data)

        Returns:
            Any: Data for the specified role and index.
        """
        if not index.isValid() or index.row() not in range(len(self._images)):
            return None

        if role == Qt.ItemDataRole.DisplayRole:
            # Use the base filename from the file path for more informative display
            file_path = self._images[index.row()].metadata.filePath
            if file_path:
                base_name = os.path.basename(file_path)
                return os.path.splitext(base_name)[0]  # Return filename without extension
            else:
                # Fallback to driver if no file path is available
                return self._images[index.row()].metadata.driver
        if role == Qt.ItemDataRole.DecorationRole:
            # return a small preview of the image
            return self._images[index.row()].getRasterDataSlice(
                self._images[index.row()].defaultBand.values
            )
        if role == Qt.ItemDataRole.UserRole:
            return self._images[index.row()]

        return None

    def _appendImage(self, image):
        """Appends a new Image to the manager. Primarily for internal use.
        Creating/adding a new image should be done through newImage().

        Returns:
            QModelIndex: Index of the newly added image.
        """

        if image in self._images:
            logger.warning(f"Image {image} already exists in ImageManager.")
            return self.index(self._images.index(image))

        self.beginInsertRows(QtCore.QModelIndex(), self.rowCount(), self.rowCount())
        self._images.append(image)
        self.endInsertRows()

        image.sigImageChanged.connect(self._imageChangedReceiver)

        return self.index(self.rowCount() - 1)

    def removeImage(self, row):
        """Removes the image at the specified row."""
        self.beginRemoveRows(QtCore.QModelIndex(), row, row)
        self._images.pop(row)
        self.endRemoveRows()

    def _imageChangedReceiver(self, imageModel):
        """Handles the imageChanged signal"""
        self.dataChanged.emit(self.index(self._images.index(imageModel)))
