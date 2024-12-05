"""
This module contains the `ImageManager` class, which manages a collection of images.
It provides methods to add, remove, and link images, and integrates with Qt's model/view framework.

Classes:
    ImageManager: Manages a collection of `ImageModel` instances.
"""
# standard library
from pathlib import Path
import logging

# third-party imports
from PyQt6 import QtCore, QtWidgets, QtGui
from PyQt6.QtCore import Qt

# local imports
from src.imageloaders.abstractimageloader import AbstractImageLoader
from models.imagemodel import ImageModel
from models.imagedatatype import ImageDataType

logger = logging.getLogger(__name__)


class ImageManager(QtCore.QAbstractListModel):
    """
    Manages a collection of images, providing an interface for adding, removing, and linking images.
    Inherits from QAbstractListModel to integrate with Qt's model/view framework.

    Attributes:
        __images (list): List of ImageModel instances managed by this class.
        links (list): List of tuples representing linked images.

    Methods:
        __init__(images=None, parent=None):
            Initializes the ImageManager with an optional list of images.

        newImage(filepath):
            Creates a new ImageModel from the given file path and appends it to the manager.

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

        linkImages(image1, image2):
            Links two images together.

        imageChangedReceiver(imageModel):
            Handles the imageChanged signal and updates linked images
    """

    def __init__(self, images=None, parent=None):
        """
        Initializes the ImageManager with an optional list of images.

        Args:
            images (list, optional): List of ImageModel instances. Defaults to None.
            parent (QObject, optional): Parent object. Defaults to None.
        """
        super().__init__(parent)
        self.__images = images if images else []

        self.links = []

    def newImage(self, filepath):
        """
        Creates a new ImageModel from the given file path and appends it to the manager.

        Args:
            filepath (str): Path to the image file.

        Returns:
            QModelIndex: Index of the newly added image.

        Raises:
            ValueError: If the file type is not supported.
        """
        # TODO: possibly need more complex system to determine file type.
        #  right now its just based on the file extension
        if filepath is None:
            logger.error("No file path provided")
            return None

        imageType = str(Path(filepath).suffix.strip())

        for c in AbstractImageLoader.subclasses:
            if imageType in c.imageType:
                # load() returns a tuple, so we unpack it (*) to pass to ImageModel
                img = ImageModel(*c(filepath).load())
                self.appendImage(img)
                logger.info("Loaded image - " + str(img))
                return img  # return the new image

        # if no image type is found, raise an error
        error = ValueError(f"Bad file type {imageType}")
        logger.error(error)
        raise error

    def rowCount(self, parent=QtCore.QModelIndex()):
        """
        Returns the number of images managed by this class.

        Args:
            parent (QModelIndex, optional): Parent index. Defaults to QModelIndex().

        Returns:
            int: Number of images.
        """
        return len(self.__images)

    def index(self, row, column=0, parent=QtCore.QModelIndex()):
        """
        Returns the index of the image at the specified row and column.

        Args:
            row (int): Row number.
            column: Unused. But required by the method signature. Defaults to 0
            parent: Unused. But required by the method signature. Defaults to QModelIndex()
        Returns:
            QModelIndex: Index of the image.
        """
        return self.createIndex(row, column, self.__images[row])

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        """
        Returns the data for the specified role and index.

        Args:
            index (QModelIndex): Index of the item.
            role (Qt.ItemDataRole): Role for which data is requested.
                role options are defined in ImageDataType.
                 - DisplayRole: Text representation of the item for display. (str)
                 - UserRole: The entire image instance (ImageModel)
                 - DecorationRole: image preview data (subset of raster data)
                 - RASTER_DATA: Raw image raster data. (numpy array)
                 - METADATA: Metadata for the item (Metadata instance)
                 - BANDS: Bands for the item (list)
                 - STRETCH: Stretch for the item (list)
                 - HISTOGRAM: Histogram for the item (HistogramLUTItem)


        Returns:
            Any: Data for the specified role and index.
        """
        if not index.isValid() or index.row() not in range(len(self.__images)):
            return None

        if role == Qt.ItemDataRole.DisplayRole:
            # eventually the image metadata should probably contain a custom name
            return self.__images[index.row()].metadata.driver

        if role == Qt.ItemDataRole.UserRole:
            return self.__images[index.row()]

        if role == Qt.ItemDataRole.DecorationRole:
            # NOTE: This returns a numpy array
            # instead of the standard convention of QPixmap, QIcon, or QColor
            return self.__images[index.row()].imageSlice

        if role == ImageDataType.RASTER_DATA:
            return self.__images[index.row()].rasterData

        if role == ImageDataType.METADATA:
            return self.__images[index.row()].metadata

        if role == ImageDataType.BANDS:
            return self.__images[index.row()].bands

        if role == ImageDataType.STRETCH:
            return self.__images[index.row()].stretch

        if role == ImageDataType.HISTOGRAM:
            return self.__images[index.row()].histogram

        return None

    def appendImage(self, imageModel):
        """
        Appends a new ImageModel to the manager. Primarily for internal use.
        Creating/adding a new image should be done through newImage().

        Args:
            imageModel (ImageModel): ImageModel instance to append.

        Returns:
            QModelIndex: Index of the newly added image.

        Raises:
            TypeError: If the imageModel is not a subclass of ImageModel.
        """
        if not issubclass(type(imageModel), ImageModel):
            raise TypeError("ImageModel must be a subclass of AbstractImageModel. "
                            "ImageModel Type: ", type(imageModel))

        if imageModel in self.__images:
            logger.warning(f"Image {imageModel} already exists in ImageManager.")
            return self.index(self.__images.index(imageModel))

        self.beginInsertRows(QtCore.QModelIndex(), self.rowCount(), self.rowCount())
        self.__images.append(imageModel)
        self.endInsertRows()

        imageModel.sigImageChanged.connect(self.imageChangedReceiver)

        return self.index(self.rowCount() - 1)

    def removeImage(self, row):
        """
        Removes the image at the specified row.

        Args:
            row (int): Row number of the image to remove.
        """
        self.beginRemoveRows(QtCore.QModelIndex(), row, row)
        self.__images.pop(row)
        self.endRemoveRows()

    def linkImages(self, image1, image2):
        """
        Links two images together.

        Args:
            image1 (ImageModel): First image to link.
            image2 (ImageModel): Second image to link.
        """

        if image1 not in self.__images and image2 not in self.__images:
            logger.error(f"Link Error: Neither Image not in ImageManager.  ({image1}, {image2})")
            return

        if image1 not in self.__images:
            logger.error(f"Link Error: Image 1 not in ImageManager. ({image1})")
            return

        if image2 not in self.__images:
            logger.error(f"Link Error: Image 2 not in ImageManager.  ({image2})")
            return

        if image1 == image2:
            logger.error(f"Link Error: Cannot link an image to itself. ({image1})")
            return

        self.links.append((image1, image2))

    def imageChangedReceiver(self, imageModel):
        """
        Handles the imageChanged signal and updates linked images.

        Args:
            imageModel (ImageModel): ImageModel instance that changed.
        """
        linkedImages = [link for link in self.links if imageModel in link]
        for link in linkedImages:
            if link[0] == imageModel:
                self.dataChanged.emit(self.index(self.__images.index(link[1])))
            else:
                self.dataChanged.emit(self.index(self.__images.index(link[0])))

        self.dataChanged.emit(self.index(self.__images.index(imageModel)))
