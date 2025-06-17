# third party imports
import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, pyqtSlot

# local imports
from core.data import ProjectContext
from core.entities import Metadata


class BandViewModel(QObject):
    """Simple ViewModel for the band view/editor.

    This handles all the business logic and interaction with the ProjectContext.
    To help with performance, it limits the frequency that the Band can be updated,
    """

    sigBandChanged = pyqtSignal(float, float, float)

    def __init__(self, proj: ProjectContext, imageIndex, parent=None):
        super().__init__(parent)
        self.proj = proj
        self.imageIndex = imageIndex
        self.bandIndex = 0
        self.wavelengthType = self.proj.getImage(
            self.imageIndex
        ).metadata.wavelengths_type
        if self.proj.getImage(self.imageIndex).metadata.wavelengths_type is str:
            self.bounds = (0, self.getBandCount() - 1)
            self.useWavelengthIndeces = True
        else:
            self.bounds = (self.getWavelengthAt(0), self.getWavelengthAt(-1))
            self.useWavelengthIndeces = False

        self._pendingBandValues = (None, None, None)
        self._updateInterval = 20
        self.isDragging = False

        self._ignoreProjectUpdates = False

        self._initTimer()
        self._connectSignals()

    def _initTimer(self):
        """Initializes the timer that will be used to debounce the band updates."""
        self.updateTimer = QTimer()
        self.updateTimer.setInterval(self._updateInterval)
        self.updateTimer.setSingleShot(True)

    def _connectSignals(self):
        """all signal callbacks are connected here."""
        self.updateTimer.timeout.connect(self._commitBandUpdate)
        self.proj.sigDataChanged[
            int, ProjectContext.ChangeType, ProjectContext.ChangeModifier
        ].connect(self._handleDataChanged)

    def getWavelengthAt(self, index) -> float | str:
        """returns the wavelength at the given index."""
        return self.proj.getImage(self.imageIndex).metadata.wavelengths[index]

    def getIndexOfWavelength(self, wavelength: float | str) -> int:
        """returns the index of the given wavelength."""
        # if the wavelengths are strings, then the value is already the index
        if self.getMetadata().wavelengths_type == str:
            return int(wavelength)
        # otherwise the slider value is a float and we need to find the closest wavelength
        return np.abs(
            self.proj.getImage(self.imageIndex).metadata.wavelengths - wavelength
        ).argmin()

    def selectBand(self, bandIndex):
        """selects a new band from the image."""
        self.bandIndex = bandIndex
        r, g, b = self.proj.getImage(self.imageIndex).band[self.bandIndex].toList()
        self.sigBandChanged.emit(r, g, b)

    def getBounds(self):
        """returns the bounds of the image."""
        return self.bounds

    def getSelectedBand(self):
        """requests the band corresponding to bandIndex, and returns it."""
        return self.proj.getImage(self.imageIndex).band[self.bandIndex]

    def getBandCount(self):
        """gets the number of band values in the image."""
        print(self.proj.getImage(self.imageIndex).metadata.bandCount)
        return self.proj.getImage(self.imageIndex).metadata.bandCount - 1

    def updateBand(self, r=None, g=None, b=None):
        """Begins a debounced band update. Since the slider value is constantly
        changing when being moved, this waits until the change is complete"""

        self._pendingBandValues = (
            r if r else None,
            g if g else None,
            b if b else None,
        )
        if not self.isDragging:
            self.isDragging = True
            self.updateTimer.start(20)

    @pyqtSlot()
    def _commitBandUpdate(self):
        """Commits the debounced slider values to the ProjectContext."""
        self.isDragging = False
        self._ignoreProjectUpdates = True

        r, g, b = [
            self.getIndexOfWavelength(value) if value is not None else None
            for value in self._pendingBandValues
        ]
        self.proj.updateBand(self.imageIndex, self.bandIndex, r=r, g=g, b=b)

    @pyqtSlot(int, ProjectContext.ChangeType, ProjectContext.ChangeModifier)
    def _handleDataChanged(self, index, changeType, changeModifier):
        """receives ProjectContext updates. Check if the update pertains to us."""

        if self._ignoreProjectUpdates:
            # if we were the one that caused the update, ignore it
            self._ignoreProjectUpdates = False
            return

        if index != self.imageIndex:
            return
        if changeType is not ProjectContext.ChangeType.BAND:
            return
        r, g, b = self.proj.getImage(self.imageIndex).band[self.bandIndex].toList()
        self.sigBandChanged.emit(r, g, b)

    def getMetadata(self):
        return self.proj.getImage(self.imageIndex).metadata
