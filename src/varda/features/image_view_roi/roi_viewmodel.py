import logging
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QMessageBox

from varda.core.roi_utils import ROIStatistics
from varda.project import ProjectContext
from varda.features.components.raster_view.roi_display_controller import (
    ROIDisplayController,
)


logger = logging.getLogger(__name__)


class ROIViewModel(QObject):
    """
    View model for ROI management.

    Acts as an intermediary between the ROI View and the ProjectContext/ROIManager.
    Handles business logic and data transformation for the UI.
    """

    # Signals
    roiAdded = pyqtSignal(str)  # Emitted when an ROI is added (passes ROI ID)
    roiRemoved = pyqtSignal(str)  # Emitted when an ROI is removed (passes ROI ID)
    roiUpdated = pyqtSignal(str)  # Emitted when an ROI is updated (passes ROI ID)
    imageChanged = pyqtSignal(int)  # Emitted when the active image changes

    def __init__(self, proj: ProjectContext, imageIndex: int, parent=None):
        super().__init__(parent)
        self.proj = proj
        self.imageIndex = imageIndex
        self.view = None

        # Initialize the ROI display controller
        self._displayController = ROIDisplayController(self)

        # Connect display controller signals
        self._displayController.roiHighlighted.connect(self.roiUpdated)
        self._displayController.roiSelected.connect(self.roiUpdated)

        self.proj.roiManager.sigROIUpdated.connect(self.roiUpdated)
        self.proj.roiManager.sigROIAdded.connect(self.roiAdded)
        self.proj.roiManager.sigROIRemoved.connect(self.roiRemoved)
        logger.debug(f"ROI ViewModel initialized for image {imageIndex}")

    def getDisplayController(self) -> ROIDisplayController:
        """Get the ROI display controller for external registration of viewports"""
        return self._displayController

    def setView(self, view):
        """Set reference to the ROI View"""
        self.view = view

    def updateImageIndex(self, imageIndex):
        """Update the current image index"""
        if self.imageIndex != imageIndex:
            self.imageIndex = imageIndex
            self.imageChanged.emit(imageIndex)
            logger.debug(f"ROI ViewModel image changed to {imageIndex}")

            # Refresh ROI display for new image
            self.refreshRoiDisplay()

    def getROIs(self, imageIndex=None):
        """Get all ROIs for the specified image (default is current image)"""
        idx = imageIndex if imageIndex is not None else self.imageIndex
        rois = self.proj.roiManager.getROIsForImage(idx)
        logger.debug(f"Got ROIs for image {idx}, IDs: {[roi.id for roi in rois]}")
        return self.proj.roiManager.getROIsForImage(idx)

    def getRoi(self, roiId):
        """Get a specific ROI by ID"""
        return self.proj.roiManager.getROI(roiId)

    def addRoi(self, roi):
        """Add a new ROI"""
        # Set the source image index
        roi.sourceImageIndex = self.imageIndex

        # Add to ROI manager
        roiId = self.proj.roiManager.addROI(roi, [self.imageIndex])
        if roiId:
            # Refresh the display to show the new ROI
            self.refreshRoiDisplay()
            self.roiAdded.emit(roiId)
        return roiId

    def removeRoi(self, imageIndex, roiIndex):
        """Remove an ROI by image index and table row index"""
        rois = self.getROIs(imageIndex)
        if roiIndex < len(rois):
            roi = rois[roiIndex]
            roiId = roi.id

            # Remove from project
            result = self.proj.roiManager.removeROI(roiId)
            if result:
                # Refresh the display to remove the ROI
                self.refreshRoiDisplay()
                self.roiRemoved.emit(roiId)
            return result
        return False

    def updateRoi(self, roiId, **properties):
        """Update ROI properties"""
        # Get the ROI entity
        roi = self.getRoi(roiId)
        if not roi:
            logger.warning(f"ROI {roiId} not found")
            return False

        # Update the ROI entity properties directly
        for key, value in properties.items():
            if hasattr(roi, key):
                setattr(roi, key, value)
            else:
                logger.warning(f"Unknown ROI property: {key}")

        # Update in ROI manager
        result = self.proj.roiManager.updateROI(roiId, roi)
        if result:
            # Update the display controller with the updated ROI
            self._displayController.updateRoi(roi)
            self.roiUpdated.emit(roiId)
        return result

    def updateRoiVisibility(self, roiId, visible):
        """Update ROI visibility"""
        return self.updateRoi(roiId, visible=visible)

    def highlightRoi(self, roiId):
        """Highlight a specific ROI"""
        self._displayController.highlightRoi(roiId)

    def showAllROIs(self):
        """Show all ROIs"""
        rois = self.getROIs()
        for roi in rois:
            if not roi.visible:
                roi.visible = True
                self.proj.roiManager.updateROI(roi.id, roi)
        self.refreshRoiDisplay()

    def hideAllROIs(self):
        """Hide all ROIs"""
        rois = self.getROIs()
        for roi in rois:
            if roi.visible:
                roi.visible = False
                self.proj.roiManager.updateROI(roi.id, roi)
        self.refreshRoiDisplay()

    def startBlinking(self):
        """Start ROI blinking animation"""
        self._displayController.startBlinking()

    def stopBlinking(self):
        """Stop ROI blinking animation"""
        self._displayController.stopBlinking()

    def isBlinking(self):
        """Check if ROI blinking is active"""
        return self._displayController.isBlinking()

    def refreshRoiDisplay(self):
        """Refresh the ROI display for the current image"""
        rois = self.getROIs(self.imageIndex)
        self._displayController.displayRoisForImage(rois)

    def addRoiCustomField(self, roiId, fieldName, value):
        """Add a custom field to an ROI"""
        roi = self.getRoi(roiId)
        if roi:
            roi.setCustomValue(fieldName, value)
            result = self.proj.roiManager.updateROI(roiId, roi)
            if result:
                self.roiUpdated.emit(roiId)
            return result
        return False

    def updateRoiCustomValue(self, roiId, fieldName, value):
        """Update a custom field value for an ROI"""
        return self.addRoiCustomField(roiId, fieldName, value)

    def plotRoiSpectrum(self, roiId):
        """Plot the spectrum of an ROI"""
        try:
            # Get the ROI
            roi = self.getRoi(roiId)
            if not roi or roi.meanSpectrum is None:
                QMessageBox.warning(
                    None,
                    "No Spectrum",
                    "This ROI doesn't have spectrum data available.",
                )
                return

            # Get wavelength data from the image
            image = self.proj.getImage(self.imageIndex)
            wavelengths = image.metadata.wavelengths

            # Create or reuse the pixel plot window
            if not hasattr(self, "pixelPlotWindow") or self.pixelPlotWindow is None:
                from varda.gui.widgets.image_plot_widget import ImagePlotWidget

                self.pixelPlotWindow = ImagePlotWidget()

            # Update the plot with ROI data
            self.pixelPlotWindow.updatePlot(
                wavelengths, roi.meanSpectrum, f"ROI {roi.name}"
            )
            self.pixelPlotWindow.show()
            self.pixelPlotWindow.raise_()  # Bring to front

        except Exception as e:
            logger.error(f"Error plotting ROI spectrum: {e}")
            QMessageBox.warning(
                None, "Plot Error", f"Error plotting spectrum: {str(e)}"
            )

    def calculateRoiStatistics(self, roiId):
        """Calculate detailed statistics for an ROI"""

        roi = self.getRoi(roiId)
        if not roi:
            logger.warning(f"ROI {roiId} not found")
            return None

        # Get the image data
        image = self.proj.getImage(self.imageIndex)

        # Calculate statistics
        stats = ROIStatistics.getROIStats(roi, image)

        # Store statistics in the ROI for future reference
        roi.setCustomValue("statistics", stats.getSummary())
        self.proj.roiManager.updateROI(roiId, roi)

        # Signal that the ROI has been updated
        self.roiUpdated.emit(roiId)

        return stats
