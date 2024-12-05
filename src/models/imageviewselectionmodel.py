import logging

from PyQt6.QtCore import QObject, pyqtSignal


from src.models.imagemodel import ImageModel
logger = logging.getLogger(__name__)


class ImageViewSelectionModel(QObject):
    """
    Model for managing the selection of bands and stretches in an image model.

    Attributes:
        sigBandChanged (pyqtSignal): Signal emitted when the band selection changes.
        sigStretchChanged (pyqtSignal): Signal emitted when the stretch selection changes.

    Methods:
        currentBand(): Gets the currently selected band.
        currentStretch(): Gets the currently selected stretch.
        selectBand(index): Selects a new band by index and updates the signals.
        selectStretch(index): Selects a new stretch by index and updates the signals.
        setBand(r, g, b): Sets the values of the currently selected band.
        setStretch(minR, maxR, minG, maxG, minB, maxB): Sets the values of the
        currently selected stretch.
    """
    sigBandChanged = pyqtSignal()
    sigStretchChanged = pyqtSignal()

    def __init__(self, imageModel: ImageModel, parent=None):
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
        self._bandSignalConnection = (
            self.currentBand().sigBandChanged.connect(self.sigBandChanged)
        )

    def _unlinkBandSignal(self):
        """Unlinks the signals of the current band from the model's signals."""
        QObject.disconnect(self._bandSignalConnection)

    def _linkStretchSignal(self):
        """Links the signals of the current stretch to the model's signals."""
        self._stretchSignalConnection = (
            self.currentStretch().sigStretchChanged.connect(self.sigStretchChanged)
        )

    def _unlinkStretchSignal(self):
        """Unlinks the signals of the current stretch from the model's signals."""
        QObject.disconnect(self._stretchSignalConnection)

    def allBands(self):
        """Returns all bands in the image model.

        Returns:
            list: List of all bands in the image model.
        """
        return self._imageModel.band

    def allStretches(self):
        """Returns all stretches in the image model.

        Returns:
            list: List of all stretches in the image model.
        """
        return self._imageModel.stretch

    def currentBand(self) -> ImageModel.Band:
        """Gets the currently selected band.

        Returns:
            Band: The currently selected band.
        """
        return self._imageModel.band[self._bandIndex]

    def currentStretch(self) -> ImageModel.Stretch:
        """Gets the currently selected stretch.

        Returns:
            Stretch: The currently selected stretch.
        """
        return self._imageModel.stretch[self._stretchIndex]

    def selectBand(self, index):
        """Selects a new band by index and updates the signals.

        Args:
            index (int): The index of the band to select.
        """
        self._unlinkBandSignal()
        self._bandIndex = index
        self._linkBandSignal()
        self.sigBandChanged.emit()

    def selectStretch(self, index):
        """Selects a new stretch by index and updates the signals.

        Args:
            index (int): The index of the stretch to select.
        """
        self._unlinkStretchSignal()
        self._stretchIndex = index
        self._linkStretchSignal()
        self.sigStretchChanged.emit()

    def setBandValues(self, r, g, b):
        """Sets the values of the currently selected band.

        Args:
            r (int): The red band value.
            g (int): The green band value.
            b (int): The blue band value.
        """
        self.currentBand().set(r, g, b)

    def setStretchValues(self, minR, maxR, minG, maxG, minB, maxB):
        """Sets the values of the currently selected stretch.

        Args:
            minR (int): The minimum red stretch value.
            maxR (int): The maximum red stretch value.
            minG (int): The minimum green stretch value.
            maxG (int): The maximum green stretch value.
            minB (int): The minimum blue stretch value.
            maxB (int): The maximum blue stretch value.
        """
        self.currentStretch().set(minR, maxR, minG, maxG, minB, maxB)
