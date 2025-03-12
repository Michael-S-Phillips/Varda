# third party imports
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from PyQt6.QtWidgets import QTableWidgetItem
import numpy as np
import pyqtgraph as pg

# local imports
from core.data import ProjectContext
from core.entities.freehandROI import FreeHandROI


class ROIViewModel(QObject):
    """Simple ViewModel for ROI table.

    Handles all the logic/interaction with the ProjectContext.
    """

    def __init__(self, proj: ProjectContext, imageIndex, parent=None):
        super().__init__(parent)
        self.proj = proj
        self.imageIndex = imageIndex
        self.rasterView = None
        
        # Store the ROI table (UI widget)
        self.roiTable = None  # Assume this will be set externally
        self._connectSignals()

    def _connectSignals(self):
        """Connect signals from the project context."""
        self.proj.sigDataChanged.connect(self._onDataChanged)

    def setRasterView(self, rasterView):
        """Will associate the place to draw an ROI with rasterView"""
        self.rasterView = rasterView

    def startDrawingROI(self):
        """Start the ROI drawing process."""
        if self.rasterView:
            self.rasterView.startNewROI()

    def notifyROIAdded(self, color):
        """
        Notify that a new ROI has been added.
        Updates the ROI table with the ROI's details, including its color.
        """
        rois = self.proj.getROIs(self.imageIndex)
        last_roi = rois[-1]

        # Update the ROI table
        if self.roiTable:
            last_index = len(rois) - 1
            self.roiTable.insertRow(last_index)
            self.roiTable.setItem(last_index, 0, QTableWidgetItem(str(last_index)))
            self.roiTable.setItem(last_index, 1, QTableWidgetItem(f"Color: {last_roi.color}"))
            self.roiTable.setItem(last_index, 2, QTableWidgetItem(f"Slice Shape: {last_roi.arraySlice.shape}"))
            self.roiTable.setItem(last_index, 3, QTableWidgetItem("Data3"))  # Placeholder

    def setROITable(self, roiTable):
        """Associate a table widget with the view model."""
        self.roiTable = roiTable

    def getROIForRow(self, row):
        """
        Retrieve the FreeHandROI object associated with a given table row.
        """
        if 0 <= row < len(self.proj.getROIs(self.imageIndex)):
            print(self.proj.getROIs(self.imageIndex)[row])
        return None
    
    def plotMeanSpectrum(self, roi):
        """
        Plot the mean spectrum data for the given ROI.

        Args:
            roi (FreeHandROI): The ROI object containing the raster slice.
        """
        if roi.arraySlice is None:
            print("No data available for this ROI.")
            return

        # Compute the mean spectrum from the array slice
        #mean_spectrum = roi.arraySlice.mean(axis=(0, 1))
        # Plot the mean spectrum (using PyQtGraph or another plotting library)

        plot_window = pg.plot(title=f"Mean Spectrum for ROI {roi.color}")
        #plot_window.plot(mean_spectrum, pen='b')
        print(f"Plotted mean spectrum for ROI {roi.color}.")
        # dummy values
        roi.meanSpectrum = np.ndarray([1, 2, 3, 4, 5])
        self.rasterView.viewModel.proj.addPlot(roi)

    def _onDataChanged(self, index, changeType):
        """React to changes in the project context."""
        if changeType == ProjectContext.ChangeType.ROI and index == self.imageIndex:
            # Update the ROI table for this image
            self._updateROITable()

    def _updateROITable(self):
        """Update the ROI table with the current ROIs."""
        if not self.roiTable:
            return
        # Clear the existing table
        self.roiTable.setRowCount(0)
        rois = self.proj.getROIs(self.imageIndex)
        last_roi = rois[-1]

        # Populate the table with the new ROI data
        last_index = len(rois) - 1
        self.roiTable.insertRow(last_index)
        self.roiTable.setItem(last_index, 0, QTableWidgetItem(str(last_index)))
        self.roiTable.setItem(last_index, 1, QTableWidgetItem(f"{last_roi.color}"))

        # Add the "Plot mean spectrum" button
        roi_view = self.roiTable.parentWidget()
        roi_view._addPlotButtonToTable(last_index, last_roi)

        self.roiTable.setItem(last_index, 3, QTableWidgetItem("Data3")) 

    # selectROI

    # getSelectedROI

    # loadROI data

    # handle ROI change (from project context)

    # def selectBand(self, bandIndex):
    #     """selects a new band from the image."""
    #     self.bandIndex = bandIndex
    #     self.sigBandChanged.emit()

    # def getSelectedBand(self):
    #     """requests the band corresponding to bandIndex, and returns it."""
    #     return self.proj.getImage(self.imageIndex).band[self.bandIndex]

    # def getBandCount(self):
    #     """gets the number of band values in the image."""
    #     return self.proj.getImage(self.imageIndex).metadata.bandCount - 1

    # def updateBand(self, r=None, g=None, b=None):
    #     """Begins a debounced band update. Since the slider value is constantly
    #     changing when being moved, this waits until the change is complete"""
    #     self._pendingBandValues = (
    #         int(r) if r else None,
    #         int(g) if g else None,
    #         int(b) if b else None,
    #     )
    #     if not self.isDragging:
    #         self.isDragging = True
    #         self.updateTimer.start(20)

    # def _commitBandUpdate(self):
    #     """Commits the debounced slider values to the ProjectContext."""
    #     r, g, b = self._pendingBandValues
    #     self.proj.updateBand(self.imageIndex, self.bandIndex, r=r, g=g, b=b)
    #     self.isDragging = False

    # def _handleDataChanged(self, index, changeType):
    #     """receives ProjectContext updates. Check if the update pertains to us."""
    #     if index != self.imageIndex:
    #         return
    #     if changeType is not ProjectContext.ChangeType.BAND:
    #         return
    #     r, g, b = self.proj.getImage(self.imageIndex).band[self.bandIndex].toList()
    #     self.sigBandChanged.emit(r, g, b)