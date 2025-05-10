# third party imports
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from PyQt6.QtWidgets import QTableWidget, QTableWidgetItem, QPushButton
import numpy as np
import pyqtgraph as pg

# local imports
from core.data import ProjectContext
from core.entities.freehandROI import FreeHandROI


class ROIViewModel(QObject):
    def __init__(self, proj: ProjectContext, imageIndex, parent=None):
        super().__init__(parent)
        self.proj = proj
        self.imageIndex = imageIndex
        self.rasterView = None
        self.view = None  # <-- reference to ROIView
        self._connectSignals()

    def _connectSignals(self):
        self.proj.sigDataChanged.connect(self._onDataChanged)

    def setRasterView(self, rasterView):
        self.rasterView = rasterView

    def setView(self, view):
        """Connect the view so we can trigger table updates."""
        self.view = view

    def startDrawingROI(self):
        if self.rasterView:
            self.rasterView.startNewROI()

    def plotMeanSpectrum(self, roi):
        if roi.arraySlice is None:
            print("No data available for this ROI.")
            return
        plot_window = pg.plot(title=f"Mean Spectrum for ROI {roi.color}")
        print(f"Plotted mean spectrum for ROI {roi.color}.")
        roi.meanSpectrum = np.ndarray([1, 2, 3, 4, 5])
        self.proj.addPlot(roi)

    def getROIForRow(self, row):
        rois = self.proj.getROIs(self.imageIndex)
        if 0 <= row < len(rois):
            return rois[row]
        return None

    def updateImageIndex(self, new_image_index):
        """Update the image index and refresh the view."""
        print(f"[DEBUG] Updating ROI view from image {self.imageIndex} to {new_image_index}")
        # Update the image index
        self.imageIndex = new_image_index

        # Get ROIs for the new image
        rois = self.proj.getROIs(self.imageIndex)

        # Update the view with the new ROIs
        if self.view:
            print(f"[DEBUG] Updating ROI table with {len(rois)} ROIs")
            self.view.updateROITable(rois)

    def _onDataChanged(self, index, changeType):
        if changeType == ProjectContext.ChangeType.ROI and index == self.imageIndex:
            if self.view:
                self.view.updateROITable(self.proj.getROIs(self.imageIndex))