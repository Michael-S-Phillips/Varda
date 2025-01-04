from PyQt6.QtWidgets import QWidget, QComboBox, QVBoxLayout

from core.data import ProjectContext


class BandSelector(QComboBox):
    def __init__(self, proj: ProjectContext, imageIndex, parent=None):
        super().__init__(parent)
        self.proj = proj
        self.imageIndex = imageIndex

        self._populateComboBox()

    def _populateComboBox(self):
        self.clear()
        self.addItems([band.name for band in self.proj.getImage(self.imageIndex).band])

    def setImageIndex(self, imageIndex):
        """updates selector to use a new image.

        this changes which image the selector reads from. it will refresh its
        contents to match the new data.

        Args:
            imageIndex: the index of the new image to use.

        """
        self.imageIndex = imageIndex
        self._populateComboBox()


class StretchSelector(QComboBox):
    def __init__(self, proj: ProjectContext, imageIndex, parent=None):
        super().__init__(parent)
        self.proj = proj
        self.imageIndex = imageIndex

        self._populateComboBox()

    def _populateComboBox(self):
        self.clear()
        self.addItems(
            [stretch.name for stretch in self.proj.getImage(self.imageIndex).stretch]
        )

    def setImageIndex(self, imageIndex):
        """updates selector to use a new image.

        this changes which image the selector reads from. it will refresh its
        contents to match the new data.

        Args:
            imageIndex: the index of the new image to use.
        """
        self.imageIndex = imageIndex
        self._populateComboBox()
