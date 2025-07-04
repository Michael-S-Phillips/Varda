"""
I'm thinking maybe we can just use this viewmodel for most of the components.
We have the GeneralImageAnalysis class instantiate a viewmodel, and pass the reference around to the other components.
Would make it easy/clean to have these components linked.
"""

from PyQt6.QtCore import QObject, pyqtSignal

import varda
from varda.core.entities import Stretch, Band


class GeneralPurposeImageViewModel(QObject):
    sigImageChanged = pyqtSignal()
    sigStretchChanged = pyqtSignal(Stretch)
    sigBandChanged = pyqtSignal(Band)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._proj = varda.app.proj
        self._stretch = None
        self._band = None
        self._imageIndex = None
        self._stretchReset = False

    @property
    def stretch(self):
        """Get the current stretch value."""
        return self._stretch

    @stretch.setter
    def stretch(self, value):
        """Set the current stretch value and emit a signal."""
        if self._stretch != value:
            self._stretch = value
            self.sigStretchChanged.emit(self._stretch)

    @property
    def band(self):
        """Get the current band value."""
        return self._band

    @band.setter
    def band(self, value):
        """Set the current band value and emit a signal."""
        if self._band != value:
            self._band = value
            self.sigBandChanged.emit(self._band)

    @property
    def imageIndex(self):
        """Get the current image index."""
        return self._imageIndex

    @imageIndex.setter
    def imageIndex(self, value):
        """Set the current image index and emit a signal."""
        if self._imageIndex != value:
            self._imageIndex = value
            self.sigImageChanged.emit()

    @property
    def projectContext(self):
        """Get the project context."""
        return self._proj

    def getImage(self):
        """Get the current image based on the image index."""
        if self._imageIndex is not None:
            return self._proj.getImage(self._imageIndex)
        return None
