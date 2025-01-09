import time

from PyQt6 import QtWidgets, QtCore


class StatusBar(QtWidgets.QStatusBar):
    """A custom widget for the statusbar.

    Lets us create more complex status messages or animations
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.animationTimer = QtCore.QTimer(self)
        self.animationIndex = None

    def showLoadingMessage(self):
        """Begins the loading message."""
        self.timeStarted = time.time()
        self.animationIndex = 0
        self.animationTimer.timeout.connect(self._updateLoadingMessage)
        self.animationTimer.start(100)  # Update every 100ms

    def _updateLoadingMessage(self):
        animationChars = ["-", "\\", "|", "/"]
        self.showMessage(f"Loading... {animationChars[self.animationIndex]}")
        self.animationIndex = (self.animationIndex + 1) % len(animationChars)

    def loadingFinished(self):
        """Ends the loading message."""
        if self.animationIndex is None:
            return
        timeElapsed = time.time() - self.timeStarted
        self.animationTimer.stop()
        self.animationTimer.timeout.disconnect(self._updateLoadingMessage)
        self.clearMessage()
        # temporary status message
        self.showMessage(
            self.tr("Image loaded in " + str(round(timeElapsed, 2)) + " seconds"),
            msecs=5000,
        )
