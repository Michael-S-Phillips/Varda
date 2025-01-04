from PyQt6.QtWidgets import QWidget, QComboBox, QVBoxLayout

from core.data import ProjectContext


class BandSelector(QComboBox):
    def __init__(self, proj: ProjectContext, imageIndex, parent=None):
        super().__init__(parent)
        self.proj = proj
        self.imageIndex = imageIndex

        self.populateComboBox()

    def populateComboBox(self):
        self.clear()
        self.addItems([band.name for band in self.proj.getImage(self.imageIndex).band])

    def setImageIndex(self, imageIndex):
        self.imageIndex = imageIndex
        self.populateComboBox()


class StretchSelector(QComboBox):
    def __init__(self, proj: ProjectContext, imageIndex, parent=None):
        super().__init__(parent)
        self.proj = proj
        self.imageIndex = imageIndex

        self.populateComboBox()

    def populateComboBox(self):
        self.clear()
        self.addItems(
            [stretch.name for stretch in self.proj.getImage(self.imageIndex).stretch]
        )

    def setImageIndex(self, imageIndex):
        self.imageIndex = imageIndex
        self.populateComboBox()
