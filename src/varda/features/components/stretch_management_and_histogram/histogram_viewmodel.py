""" """

# third party imports
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from varda.core.data import ProjectContext

# local imports
import logging

from varda.core.entities import Stretch

logger = logging.getLogger(__name__)


class HistogramViewModel(QObject):
    """Simple ViewModel for the stretch view/editor. This handles all the business
    logic and interaction with the ProjectContext.
    """

    sigBandChanged = pyqtSignal()
    sigStretchChanged = pyqtSignal(Stretch)

    def __init__(self, proj: ProjectContext, imageIndex, parent=None):
        super().__init__(parent)
        self.proj = proj
        self.index = imageIndex
        self.stretchIndex = 0
        self.bandIndex = 0

        self.blockSignals = False

        self._isUpdatingStretch = False
        self._connectSignals()

    def _connectSignals(self):
        self.proj.sigDataChanged[
            int, ProjectContext.ChangeType, ProjectContext.ChangeModifier
        ].connect(self._handleDataChanged)

    def selectBand(self, stretchIndex):
        """selects a new stretch from the image."""
        self.stretchIndex = stretchIndex
        self.sigBandChanged.emit()

    def selectStretch(self, stretchIndex):
        """selects a new stretch from the image."""
        self.stretchIndex = stretchIndex
        self._handleDataChanged(
            self.index,
            ProjectContext.ChangeType.STRETCH,
            ProjectContext.ChangeModifier.UPDATE,
        )

    def getSelectedBand(self):
        """requests the stretch corresponding to stretchIndex, and returns it."""
        return self.proj.getImage(self.index).band[self.bandIndex]

    def getSelectedStretch(self):
        """requests the stretch corresponding to stretchIndex, and returns it."""
        return self.proj.getImage(self.index).stretch[self.stretchIndex]

    def getRasterFromBand(self):
        """Using the currently selected band, creates and returns a subset of the
        raster data so that it can be used as a standard rgb image."""
        band = self.getSelectedBand()
        return self.proj.getImage(self.index).raster[:, :, [band.r, band.g, band.b]]

    def updateStretch(
        self, minR=None, maxR=None, minG=None, maxG=None, minB=None, maxB=None
    ):
        """tells the project to update the stretch configuration with new values."""
        self._isUpdatingStretch = True
        self.proj.updateStretch(
            self.index,
            self.stretchIndex,
            name=None,
            minR=minR,
            maxR=maxR,
            minG=minG,
            maxG=maxG,
            minB=minB,
            maxB=maxB,
        )

    @pyqtSlot(int, ProjectContext.ChangeType, ProjectContext.ChangeModifier)
    def _handleDataChanged(self, index, changeType, changeModifier):
        if index != self.index:
            return
        if changeModifier is not ProjectContext.ChangeModifier.UPDATE:
            return

        if changeType is ProjectContext.ChangeType.BAND:
            self.sigBandChanged.emit()
        elif changeType is ProjectContext.ChangeType.STRETCH:

            # don't do anything if we were the one that caused the change.
            if self._isUpdatingStretch:
                logger.debug("Currently Updating Stretch. Ignoring Project update")
                self._isUpdatingStretch = False
                return

            stretch = self.getSelectedStretch()
            logger.debug(
                "Stretch changed: (%.6f, %.6f, %.6f, %.6f, %.6f, %.6f)",
                stretch.minR,
                stretch.maxR,
                stretch.minG,
                stretch.maxG,
                stretch.minB,
                stretch.maxB,
            )
            self.sigStretchChanged.emit(stretch)
