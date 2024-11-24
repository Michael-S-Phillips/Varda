
# standard imports

# third-party imports
from PyQt6 import QtCore, QtWidgets, QtGui
from PyQt6.QtCore import Qt
import pyqtgraph as pg
import numpy as np
import cv2

# local imports
from models import AbstractImageModel


class ImageListModel(QtCore.QAbstractListModel):

    def __init__(self, images=None, parent=None):
        super().__init__(parent)
        self.images = images if images else []

    def rowCount(self, parent=QtCore.QModelIndex()):
        return len(self.images)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self.images)):
            return None

        img = self.images[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return img.meta.driver
        if role == Qt.ItemDataRole.UserRole:
            return img  # Return the specific ImageModel
        if role == Qt.ItemDataRole.DecorationRole:
            # NOTE: This returns a numpy array instead of
            # the standard convention of QPixmap, QIcon, or QColor
            return img.imageSlice

        return None

    def addImage(self, imageModel):
        if not issubclass(type(imageModel), AbstractImageModel):
            raise TypeError("ImageModel must be a subclass of AbstractImageModel. "
                            "ImageModel Type: ", type(imageModel))
        self.beginInsertRows(QtCore.QModelIndex(), self.rowCount(), self.rowCount())
        self.images.append(imageModel)
        self.endInsertRows()

    def removeImage(self, row):
        self.beginRemoveRows(QtCore.QModelIndex(), row, row)
        self.images.pop(row)
        self.endRemoveRows()
