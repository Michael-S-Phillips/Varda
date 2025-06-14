import numpy as np
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import Qt, pyqtSignal, QEvent, QPoint
import pyqtgraph as pg
import logging

from varda.core.data import ProjectContext

logger = logging.getLogger(__name__)


class ImagePlotWidget(QWidget):
    """
    A widget for plotting data from an image.
     Right now this is just the spectral data for a certain pixel, but later we could add methods for other types of plots.
     It Can be used either as a small embedded widget or a popup window.
    """

    sigClicked = pyqtSignal()

    _pressPos = None  # Store the position of the mouse press for click detection

    def __init__(
        self,
        proj: ProjectContext = None,
        imageIndex=None,
        isWindow: bool = False,
        parent=None,
    ):
        super().__init__(parent)
        self.isWindow = isWindow

        # unique setup depending on whether this is being used as a window or an embedded widget
        if self.isWindow:
            self.setWindowTitle("Pixel Spectrum")
            self.setMinimumSize(600, 300)
            self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        else:
            self.setMinimumHeight(180)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self.proj = proj
        self.imageIndex = imageIndex

        # initialize the plot
        self.plot_widget = pg.PlotWidget(title="Pixel Spectrum")
        self.plot_widget.setLabels(left="Intensity", bottom="Wavelength (nm)")
        self.plot_widget.showGrid(x=True, y=True)
        self.plot_widget.addLegend()
        scene = self.plot_widget.getViewBox().scene()
        scene.installEventFilter(self)
        # self.plot_widget.installEventFilter(self)
        # create layout
        self.layout = QVBoxLayout()
        self.layout.addWidget(self.plot_widget)
        self.setLayout(self.layout)

        # if a project context and image index is provided, automatically set the image
        if self.proj is not None and self.imageIndex is not None:
            self.setImage(self.imageIndex)

        self.show()
        logger.debug("PixelPlotWindow initialized")

    def eventFilter(self, obj, event):
        """Filter events for the plot widget to handle clicks and mouse releases."""
        # handle mouse press
        if event.type() == QEvent.Type.GraphicsSceneMousePress:
            self._pressPos = event.scenePos()
            logger.debug("Mouse press event")

        # handle mouse release
        if event.type() == QEvent.Type.GraphicsSceneMouseRelease:
            logger.debug("Mouse release event")
            if (
                QPoint(event.scenePos().toPoint()) - self._pressPos.toPoint()
            ).manhattanLength() < 5:
                logger.debug("PixelPlotWidget clicked!")
                self.sigClicked.emit()
            else:
                logger.debug("PixelPlotWidget mouse release was a drag, not a click.")

        return super().eventFilter(obj, event)

    def closeEvent(self, event):
        """Handle the window close event."""
        logger.debug("PixelPlotWindow closed")
        # Ensure window is properly closed and removed from tracking
        event.accept()

    def setImage(self, imageIndex):
        """Set the image index for the plot window."""
        self.imageIndex = imageIndex
        image = self.proj.getImage(imageIndex)
        self.setWindowTitle(f"Pixel Spectrum - {image.metadata.name}")

    def showPixelSpectrum(self, x, y, imageIndex=None):
        """
        Display the pixel spectrum for the given coordinates.
        Optionally, specify an image index. Otherwise, the current image index is used.
        """
        self.plot_widget.clear()

        if imageIndex is not None:
            self.setImage(imageIndex)

        image = self.proj.getImage(self.imageIndex)

        try:
            wavelengths = np.char.strip(image.metadata.wavelengths.astype(str)).astype(
                float
            )
        except ValueError as e:
            logger.warning(
                f"Wavelengths appear to be categorical. Generating a numeric vector of the same length."
            )
            wavelengths = np.arange(len(image.metadata.wavelengths), dtype=float)

        spectrum = image.raster[y, x, :]
        self.updatePlot(wavelengths, spectrum, (x, y))

    def updatePlot(self, wavelengths, spectrum, coords):
        """Update the plot with new spectral data."""
        self.plot_widget.clear()
        logger.debug(f"Plotting spectrum for coordinates: {coords}")
        try:
            try:
                wavelengths = np.asarray(wavelengths, dtype=float)
            except ValueError as e:
                logger.warning(
                    f"Wavelengths appear to be categorical. Generating a numeric vector of the same length."
                )
                wavelengths = np.arange(len(wavelengths), dtype=float)
            spectrum = np.asarray(spectrum, dtype=float)
            logger.debug(
                f"Wavelength range: {wavelengths.min() if len(wavelengths) > 0 else 'N/A'} - "
                + f"{wavelengths.max() if len(wavelengths) > 0 else 'N/A'} nm"
            )
            logger.debug(
                f"Spectral data range: {spectrum.min() if len(spectrum) > 0 else 'N/A'} - "
                + f"{spectrum.max() if len(spectrum) > 0 else 'N/A'}"
            )
        except ValueError as e:
            logger.error(f"Error converting data to numeric types: {e}")
            return

        self.plot_widget.plot(
            wavelengths, spectrum, pen="y", name=f"({coords[0]}, {coords[1]})"
        )
        self.plot_widget.setTitle(f"Pixel Spectrum at {coords}")
