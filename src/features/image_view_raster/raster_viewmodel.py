# src/features/image_view_raster/raster_viewmodel.py

# third party imports
from PyQt6.QtCore import QObject, pyqtSignal
import numpy as np
import logging

# local imports
from core.data import ProjectContext
from core.utilities.signal_utils import guard_signals

logger = logging.getLogger(__name__)


class RasterViewModel(QObject):
    """ViewModel for the RasterView.

    Manages band and stretch selections and generates RGB image data
    based on the raster data and currently selected band.

    Signals:
        sigBandChanged: Emitted when the selected band changes
        sigStretchChanged: Emitted when the selected stretch changes
        sigROIChanged: Emitted when ROIs for the image change
        sigDataUpdated: Emitted when any data changes that affects the display
    """

    sigBandChanged = pyqtSignal()
    sigStretchChanged = pyqtSignal()
    sigROIChanged = pyqtSignal()
    sigDataUpdated = pyqtSignal()  # General signal for any data changes

    def __init__(self, proj: ProjectContext, imageIndex, parent=None):
        super().__init__(parent)
        self.proj = proj
        self.imageIndex = imageIndex
        self.index = imageIndex  # For backwards compatibility
        self.bandIndex = 0
        self.stretchIndex = 0

        # Connect to project context signals
        self._connectSignals()

        # Log initial state
        logger.debug(f"RasterViewModel initialized for image {imageIndex}")
        self._logImageInfo()

    def _connectSignals(self):
        """Connect to signals from the ProjectContext."""
        self.proj.sigDataChanged.connect(self._handleDataChanged)

        # Connect our internal signals to update the general data signal
        self.sigBandChanged.connect(self.sigDataUpdated)
        self.sigStretchChanged.connect(self.sigDataUpdated)
        self.sigROIChanged.connect(self.sigDataUpdated)

    def selectBand(self, bandIndex):
        """Select a new band from the image.

        Args:
            bandIndex: The index of the band to select
        """
        if bandIndex == self.bandIndex:
            return  # No change

        self.bandIndex = bandIndex
        logger.debug(f"Selected band {bandIndex}")
        self.sigBandChanged.emit()

    def getSelectedBand(self):
        """Get the currently selected band from the image.

        Returns:
            Band: The selected band object
        """
        return self.proj.getImage(self.index).band[self.bandIndex]

    def getRasterFromBand(self):
        """Get a subset of the raster data for RGB display.

        Creates a 3-band subset of the raster data based on the RGB channels
        defined in the selected band configuration.

        Returns:
            np.ndarray: Array with shape (height, width, 3) for RGB display
        """
        band = self.getSelectedBand()

        try:
            # Get the RGB bands from the raster data
            image = self.proj.getImage(self.index)
            rgb_data = image.raster[:, :, [band.r, band.g, band.b]]

            # Handle any out-of-range values
            if np.isnan(rgb_data).any():
                logger.warning(
                    f"NaN values found in raster data for bands {[band.r, band.g, band.b]}"
                )
                rgb_data = np.nan_to_num(rgb_data)

            return rgb_data
        except IndexError as e:
            logger.error(f"Error extracting RGB bands: {e}")
            # Return a placeholder if there's an error
            image = self.proj.getImage(self.index)
            h, w = image.raster.shape[0:2]
            return np.zeros((h, w, 3))

    def selectStretch(self, stretchIndex):
        """Select a new stretch configuration.

        Args:
            stretchIndex: The index of the stretch to select
        """
        if stretchIndex == self.stretchIndex:
            return  # No change

        self.stretchIndex = stretchIndex
        logger.debug(f"Selected stretch {stretchIndex}")
        self.sigStretchChanged.emit()

    def getSelectedStretch(self):
        """Get the currently selected stretch configuration.

        Returns:
            Stretch: The selected stretch object
        """
        return self.proj.getImage(self.index).stretch[self.stretchIndex]

    @guard_signals
    def _handleDataChanged(self, index, changeType):
        """Handle data changes from the ProjectContext.

        Args:
            index: The index of the changed image
            changeType: The type of change (BAND, STRETCH, ROI)
        """
        if index != self.index:
            return

        if changeType is ProjectContext.ChangeType.BAND:
            self.sigBandChanged.emit()
        elif changeType is ProjectContext.ChangeType.STRETCH:
            self.sigStretchChanged.emit()
        elif changeType is ProjectContext.ChangeType.ROI:
            self.sigROIChanged.emit()

    def getFullDataCube(self):
        """Get the full hyperspectral data cube.

        Returns:
            np.ndarray: The complete hyperspectral data cube
        """
        return self.proj.getImage(self.index).raster

    def _logImageInfo(self):
        """Log information about the image being viewed."""
        try:
            image = self.proj.getImage(self.index)
            logger.debug(f"Image shape: {image.raster.shape}")
            logger.debug(f"Bands: {len(image.band)}")
            logger.debug(f"Stretches: {len(image.stretch)}")
        except Exception as e:
            logger.error(f"Error logging image info: {e}")
