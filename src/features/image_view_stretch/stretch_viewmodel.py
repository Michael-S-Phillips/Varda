"""

"""

# third party imports
from PyQt6.QtCore import QObject, pyqtSignal
from core.data import ProjectContext
from core.utilities.signal_utils import guard_signals

# local imports
import logging

logger = logging.getLogger(__name__)


class StretchViewModel(QObject):
    """Simple ViewModel for the stretch view/editor. This handles all the business
    logic and interaction with the ProjectContext.
    """

    sigStretchChanged = pyqtSignal()

    def __init__(self, proj: ProjectContext, imageIndex, parent=None):
        super().__init__(parent)
        self.proj = proj
        self.index = imageIndex
        self.stretchIndex = 0
        self._connectSignals()

    def _connectSignals(self):
        self.proj.sigDataChanged.connect(self._handleDataChanged)

    def selectStretch(self, stretchIndex):
        """selects a new stretch from the image."""
        self.stretchIndex = stretchIndex
        self.sigStretchChanged.emit()

    def getSelectedStretch(self):
        """requests the stretch corresponding to stretchIndex, and returns it."""
        return self.proj.getImage(self.index).stretch[self.stretchIndex]

    def updateStretch(self, minR, maxR, minG, maxG, minB, maxB):
        """Update the stretch configuration.

        Args:
            minR, maxR: Red channel min/max values
            minG, maxG: Green channel min/max values
            minB, maxB: Blue channel min/max values
        """
        # Log the current stretch
        old_stretch = self.getSelectedStretch()
        logger.debug(
            f"Updating stretch: Old: ({old_stretch.minR:.6f}, {old_stretch.maxR:.6f}, {old_stretch.minG:.6f}, {old_stretch.maxG:.6f}, {old_stretch.minB:.6f}, {old_stretch.maxB:.6f})"
        )
        logger.debug(
            f"Updating stretch: New: ({minR:.6f}, {maxR:.6f}, {minG:.6f}, {maxG:.6f}, {minB:.6f}, {maxB:.6f})"
        )

        # Check if there's an actual change
        if (
            abs(old_stretch.minR - minR) < 1e-6
            and abs(old_stretch.maxR - maxR) < 1e-6
            and abs(old_stretch.minG - minG) < 1e-6
            and abs(old_stretch.maxG - maxG) < 1e-6
            and abs(old_stretch.minB - minB) < 1e-6
            and abs(old_stretch.maxB - maxB) < 1e-6
        ):
            logger.debug("No significant change in stretch values, skipping update")
            return

        # Update the stretch in the project context
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

        # Explicitly emit the change signal
        self.sigStretchChanged.emit()

    @guard_signals
    def _handleDataChanged(self, index, changeType, changeModifier=None):
        if index != self.index:
            return
        if changeType != ProjectContext.ChangeType.STRETCH:
            return

        # guarded signal
        stretch = self.getSelectedStretch()
        self.sigStretchChanged.emit()
