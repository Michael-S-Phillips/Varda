from PyQt6 import QtCore, QtWidgets
import pyqtgraph as pg
import numpy as np


class PixelPlotWindow(QtWidgets.QWidget):
    """
    A window that displays the image with crosshairs and a plot of the spectral data for the selected pixel.
    """

    def __init__(self, raster_data, wavelength=None, parent=None):
        super().__init__(parent)
        self.raster_data = raster_data
        self.wavelength = wavelength if wavelength is not None else np.arange(raster_data.shape[2])

        self.setWindowTitle("Pixel Plot")
        self.resize(800, 600)

        # PyQtGraph Image View
        self.imageView = pg.ImageView()
        self.imageView.setImage(np.mean(self.raster_data, axis=2))  # Show an average intensity projection

        # Crosshairs
        self.crosshair_v = pg.InfiniteLine(angle=90, movable=False, pen='r')
        self.crosshair_h = pg.InfiniteLine(angle=0, movable=False, pen='r')
        self.imageView.getView().addItem(self.crosshair_v)
        self.imageView.getView().addItem(self.crosshair_h)

        # Pixel Plot
        self.pixelPlot = pg.PlotWidget(title="Pixel Spectrum")
        self.pixelPlot.setLabels(left="Intensity", bottom="Wavelength (nm)")

        # Layout
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.imageView)
        layout.addWidget(self.pixelPlot)
        self.setLayout(layout)

        # Connect mouse click to update crosshairs and plot
        self.imageView.scene.sigMouseClicked.connect(self.updatePixelPlot)

    def updatePixelPlot(self, event):
        """
        Update the pixel plot and crosshairs based on the clicked pixel.
        """
        # Map click position to image coordinates
        pos = self.imageView.getView().mapSceneToView(event.scenePos())
        x, y = int(pos.x()), int(pos.y())

        # Check bounds
        if 0 <= x < self.raster_data.shape[1] and 0 <= y < self.raster_data.shape[0]:
            # Update crosshairs
            self.crosshair_v.setPos(x)
            self.crosshair_h.setPos(y)

            # Extract spectral data for the clicked pixel
            spectral_data = self.raster_data[y, x, :]

            # Plot the spectral data
            self.pixelPlot.clear()
            self.pixelPlot.plot(self.wavelength, spectral_data, pen='y')

            # Update plot title
            self.pixelPlot.setTitle(f"Pixel Spectrum at ({x}, {y})")
