# third party imports
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, pyqtSlot

# local imports
from core.data import ProjectContext


class BandViewModel(QObject):
    """Simple ViewModel for the band view/editor.

    This handles all the business logic and interaction with the ProjectContext.
    To help with performance, it limits the frequency that the Band can be updated,
    """

    sigBandChanged = pyqtSignal(int, int, int)

    def __init__(self, proj: ProjectContext, imageIndex, parent=None):
        super().__init__(parent)
        self.proj = proj
        self.imageIndex = imageIndex
        self.bandIndex = 0

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

    def selectBand(self, bandIndex):
        """selects a new band from the image."""
        self.bandIndex = bandIndex
        r, g, b = self.proj.getImage(self.imageIndex).band[self.bandIndex].toList()
        self.sigBandChanged.emit(r, g, b)

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
            int(r) if r else None,
            int(g) if g else None,
            int(b) if b else None,
        )
        if not self.isDragging:
            self.isDragging = True
            self.updateTimer.start(20)

    @pyqtSlot()
    def _commitBandUpdate(self):
        """Commits the debounced slider values to the ProjectContext."""
        r, g, b = self._pendingBandValues

        self.isDragging = False
        self._ignoreProjectUpdates = True

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
