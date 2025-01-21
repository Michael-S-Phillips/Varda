# third party imports
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from PyQt6.QtWidgets import QTableWidgetItem

# local imports
from core.data import ProjectContext


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
            self.rasterView.startDrawingROI()

    def setROITable(self, roiTable):
        """Associate a table widget with the view model."""
        self.roiTable = roiTable

    def _onDataChanged(self, index, changeType):
        """React to changes in the project context."""
        if changeType == ProjectContext.ChangeType.ROI and index == self.imageIndex:
            # Update the ROI table for this image
            self._updateROITable()

    def _updateROITable(self):
        """Update the ROI table with the current ROIs."""
        if not self.roiTable:
            return

        # Get ROIs from the project context
        rois = self.proj.getROIs(self.imageIndex)

        # Clear the existing table
        self.roiTable.setRowCount(0)

        # Populate the table with the new ROI data
        for row_index, roi in enumerate(rois):
            self.roiTable.insertRow(row_index)

            # Fill the table with ROI data (replace placeholders as needed)
            self.roiTable.setItem(row_index, 0, QTableWidgetItem(str(row_index)))
            self.roiTable.setItem(row_index, 1, QTableWidgetItem("Data1"))  # Placeholder
            self.roiTable.setItem(row_index, 2, QTableWidgetItem("Data2"))  # Placeholder
            self.roiTable.setItem(row_index, 3, QTableWidgetItem("Data3"))  # Placeholder

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