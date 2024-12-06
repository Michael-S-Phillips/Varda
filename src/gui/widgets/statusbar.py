import time

from PyQt6 import QtWidgets, QtCore


class StatusBar(QtWidgets.QStatusBar):
    """
    A custom widget for the statusbar.
    Lets us create more complex status messages or animations without cluttering the ImageWorkspace class
    """
    def __init__(self, parent=None):
        super(StatusBar, self).__init__(parent)
        self.animationTimer = QtCore.QTimer(self)
        self.animationIndex = None

    def showLoadingMessage(self):
        self.timeStarted = time.time()
        self.animationIndex = 0
        self.animationTimer.timeout.connect(self.updateLoadingMessage)
        self.animationTimer.start(100)  # Update every 100ms

    def updateLoadingMessage(self):
        animationChars = ['-', '\\', '|', '/']
        self.showMessage(f"Loading... {animationChars[self.animationIndex]}")
        self.animationIndex = (self.animationIndex + 1) % len(animationChars)

    def loadingFinished(self):
        if self.animationIndex is None:
            return
        self.timeElapsed = time.time() - self.timeStarted
        self.animationTimer.stop()
        self.animationTimer.timeout.disconnect(self.updateLoadingMessage)
        self.clearMessage()
        # temporary status message
        self.showMessage(self.tr(
            "Image loaded in " + str(round(self.timeElapsed, 2))
            + " seconds"), msecs=5000)
