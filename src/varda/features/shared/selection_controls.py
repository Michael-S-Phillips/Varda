from PyQt6.QtCore import pyqtSlot
from PyQt6.QtWidgets import (
    QComboBox,
)

from varda.app.project import ProjectContext


class BandSelector(QComboBox):
    """Basic utility widget for listing the band configurations of an image and
    selecting one.

    Connect to the currentIndexChanged signal to be notified when the user changes
    their selection.
    """

    def __init__(self, proj: ProjectContext, imageIndex, parent=None):
        super().__init__(parent)
        self.proj = proj
        self.imageIndex = imageIndex
        self._handling_change = False
        self.proj.sigDataChanged.connect(self._onProjectDataChanged)
        self._populateComboBox()

    def _populateComboBox(self):
        self.clear()
        self.addItems([band.name for band in self.proj.getImage(self.imageIndex).band])

    def setImageIndex(self, imageIndex):
        """Updates selector to use a new image. Refreshes contents to match new data."""
        self.imageIndex = imageIndex
        self._populateComboBox()

    @pyqtSlot(int, ProjectContext.ChangeType)
    def _onProjectDataChanged(self, index, changeType):
        if self._handling_change:
            return

        if index == self.imageIndex and changeType == ProjectContext.ChangeType.STRETCH:
            self._handling_change = True
            try:
                self._populateComboBox()
            finally:
                self._handling_change = False


class StretchSelector(QComboBox):
    """Basic utility widget for listing the stretch configurations of an image and
    selecting one.

    Connect to the currentIndexChanged signal to be notified when the user changes
    their selection.
    """

    def __init__(self, proj: ProjectContext, imageIndex, parent=None):
        super().__init__(parent)
        self.proj = proj
        self.imageIndex = imageIndex

        self.proj.sigDataChanged.connect(self._onProjectDataChanged)
        self._populateComboBox()

    def _populateComboBox(self):
        self.clear()
        self.addItems(
            [stretch.name for stretch in self.proj.getImage(self.imageIndex).stretch]
        )

    def setImageIndex(self, imageIndex):
        """Updates selector to use a new image. Refreshes contents to match new data.

        Args:
            imageIndex: the index of the new image to use.
        """
        self.imageIndex = imageIndex
        self._populateComboBox()

    @pyqtSlot(int, ProjectContext.ChangeType)
    def _onProjectDataChanged(self, index, changeType):
        if index == self.imageIndex and changeType == ProjectContext.ChangeType.STRETCH:
            self._populateComboBox()
