import logging

from PyQt6.QtCore import QObject, pyqtSignal


from core.entities import Image, Band, Stretch

logger = logging.getLogger(__name__)


class ImageViewModel(QObject):
    """
    Intermediary image model for views to use. Manages active band
    and stretch selections, and emits signals when the selected band or stretch changes.

    Also serves as an access point for the rest of the image model's data. Even
    though the other data doesn't need selections. Just to maintain a clean separation.

    Attributes:
        sigImageChanged (pyqtSignal): Signal emitted when the image model changes.
        sigBandChanged (pyqtSignal): Signal emitted when the band selection changes.
        sigStretchChanged (pyqtSignal): Signal emitted when the stretch selection changes.

    Methods:
        getRasterData() -> np.ndarray:
            Returns the raw image data from the image model.
        getRasterDataSlice() -> np.ndarray:
            Returns a 3-band slice of the raster data from the image model, based on the
            view's currently selected band.
        getMetadata() -> Metadata:
            Returns the metadata from the image model.
        getAllBands() -> list:
            Returns all bands in the image model.
        getAllStretches() -> list:
            Returns all stretches in the image model.
        getCurrentBand() -> ImageModel.Band:
            Gets the currently selected band.
        getCurrentStretch() -> ImageModel.Stretch:
            Gets the currently selected stretch.
        getBandIndex() -> int:
            Gets the index of the currently selected bands.
        setBandIndex(index: int):
            Selects a new band by index and updates the signals.
        getStretchIndex() -> int:
            Gets the index of the currently selected stretch.
        setStretchIndex(index: int):
            Selects a new stretch by index and updates the signals.
        setBand(r, g, b):
            Sets the values of the currently selected band.
        setStretch(minR, maxR, minG, maxG, minB, maxB):
            Sets the values of the currently selected stretch.
    """

    sigImageChanged = pyqtSignal()
    sigBandChanged = pyqtSignal()
    sigStretchChanged = pyqtSignal()

    def __init__(self, imageModel: Image, parent=None):
        """Initializes the ImageViewSelectionModel with the given image model.

        Args:
            imageModel (ImageModel): The image model to manage.
            parent (QObject, optional): The parent object. Defaults to None.
        """
        super().__init__(parent)
        self._bandIndex = 0
        self._stretchIndex = 0
        self._imageModel = imageModel
        self._bandSignalConnection = None
        self._stretchSignalConnection = None

        self._linkBandSignal()
        self._linkStretchSignal()

    def _linkBandSignal(self):
        """Links the signals of the current band to the model's signals."""
        self._bandSignalConnection = self.getCurrentBand().sigBandChanged.connect(
            self.sigBandChanged
        )

    def _unlinkBandSignal(self):
        """Unlinks the signals of the current band from the model's signals."""
        QObject.disconnect(self._bandSignalConnection)

    def _linkStretchSignal(self):
        """Links the signals of the current stretch to the model's signals."""
        self._stretchSignalConnection = (
            self.getCurrentStretch().sigStretchChanged.connect(self.sigStretchChanged)
        )

    def _unlinkStretchSignal(self):
        """Unlinks the signals of the current stretch from the model's signals."""
        QObject.disconnect(self._stretchSignalConnection)

    def getRasterData(self):
        """
        Returns the raw image data from the image model."""
        return self._imageModel.rasterData

    def getRasterDataSlice(self):
        """Returns a 3 band slice of the raster data from the image model, based on the
        view's currently selected band."""
        return self._imageModel.getRasterDataSlice(self.getCurrentBand().values)

    def getMetadata(self):
        """
        Returns the metadata from the image model."""
        return self._imageModel.metadata

    def getAllBands(self):
        """Returns list of all bands in the image model."""
        return self._imageModel.band

    def getAllStretches(self):
        """Returns list of all stretches in the image model."""
        return self._imageModel.stretch

    def getCurrentBand(self) -> Band:
        """Returns the currently selected band."""
        return self._imageModel.band[self._bandIndex]

    def getCurrentStretch(self) -> Stretch:
        """Returns the currently selected stretch."""
        return self._imageModel.stretch[self._stretchIndex]

    def getBandIndex(self):
        """Gets the index of the currently selected band."""
        return self._bandIndex

    def setBandIndex(self, index):
        """Selects a new band by index and updates the signals."""
        self._unlinkBandSignal()
        self._bandIndex = index
        self._linkBandSignal()
        self.sigBandChanged.emit()

    def getStretchIndex(self):
        """Returns the index of the currently selected stretch."""
        return self._stretchIndex

    def setStretchIndex(self, index):
        """Selects a new stretch by index and updates the signals."""
        self._unlinkStretchSignal()
        self._stretchIndex = index
        self._linkStretchSignal()
        self.sigStretchChanged.emit()

    def setBandValues(self, r, g, b):
        """Sets the values of the currently selected band."""
        self.getCurrentBand().set(r, g, b)

    def setStretchValues(self, minR, maxR, minG, maxG, minB, maxB):
        """Sets the values of the currently selected stretch."""
        self.getCurrentStretch().set(minR, maxR, minG, maxG, minB, maxB)
