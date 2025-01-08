from PyQt6.QtWidgets import QWidget, QComboBox, QVBoxLayout

from core.data import ProjectContext


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

        self._populateComboBox()

    def _populateComboBox(self):
        self.clear()
        self.addItems([band.name for band in self.proj.getImage(self.imageIndex).band])

    def setImageIndex(self, imageIndex):
        """Updates selector to use a new image. Refreshes contents to match new data.

        Args:
            imageIndex: the index of the new image to use.
        """
        self.imageIndex = imageIndex
        self._populateComboBox()


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
