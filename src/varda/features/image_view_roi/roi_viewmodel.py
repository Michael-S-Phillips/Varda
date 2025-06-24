import logging
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QMessageBox

from varda.core.data import ProjectContext

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
        self.rasterView = None

        logger.debug(f"ROI ViewModel initialized for image {imageIndex}")

    def setView(self, view):
        """Set reference to the ROI View"""
        self.view = view

    def setRasterView(self, rasterView):
        """Set reference to the RasterView for drawing ROIs"""
        self.rasterView = rasterView

    def updateImageIndex(self, imageIndex):
        """Update the current image index"""
        if self.imageIndex != imageIndex:
            self.imageIndex = imageIndex
            self.imageChanged.emit(imageIndex)
            logger.debug(f"ROI ViewModel image changed to {imageIndex}")

    def getAllRois(self):
        """Get all ROIs associated with the current image"""
        rois = {}
        for roi in self.proj.roi_manager.get_rois_for_image(self.imageIndex):
            rois[roi.id] = roi
        return rois

    def getROIs(self, imageIndex=None):
        """Get all ROIs for the specified image (default is current image)"""
        idx = imageIndex if imageIndex is not None else self.imageIndex
        return self.proj.get_rois_for_image(idx)

    def getRoi(self, roi_id):
        """Get a specific ROI by ID"""
        return self.proj.roi_manager.get_roi(roi_id)
    
    def addRoi(self, roi):
        """Add a new ROI"""
        roi_id = self.proj.roi_manager.add_roi(roi, [self.imageIndex])
        if roi_id:
            self.roiAdded.emit(roi_id)
        return roi_id

    def removeRoi(self, roi_id):
        """Remove an ROI"""
        result = self.proj.roi_manager.remove_roi(roi_id)
        if result:
            self.roiRemoved.emit(roi_id)
        return result

    def updateRoi(self, roi_id, **properties):
        """Update ROI properties"""
        result = self.proj.roi_manager.update_roi(roi_id, **properties)
        if result:
            self.roiUpdated.emit(roi_id)
        return result

    def updateRoiVisibility(self, roi_id, visible):
        """Update ROI visibility (special case for display updates)"""
        roi = self.getRoi(roi_id)
        if roi:
            if hasattr(roi, "visible"):
                roi.visible = visible
            self.roiUpdated.emit(roi_id)
            return True
        return False

    def addRoiCustomField(self, roi_id, field_name, value):
        """Add a custom field to an ROI"""
        roi = self.getRoi(roi_id)
        if roi and hasattr(roi, "custom_data") and hasattr(roi.custom_data, "values"):
            roi.custom_data.values[field_name] = value
            self.roiUpdated.emit(roi_id)
            return True
        return False

    def updateRoiCustomValue(self, roi_id, field_name, value):
        """Update a custom field value for an ROI"""
        return self.addRoiCustomField(roi_id, field_name, value)

    def startDrawingROI(self):
        """Start the ROI drawing process"""
        if self.rasterView and hasattr(self.rasterView, "roi_drawing_manager"):
            self.rasterView.roi_drawing_manager.startDrawingROI()
        else:
            # Fallback to old method
            if self.rasterView:
                self.rasterView.startNewROI()
            else:
                logger.warning("Cannot start ROI drawing - no RasterView available")

    def plotRoiSpectrum(self, roi_id):
        """Plot the spectrum of an ROI"""
        try:
            # Get the ROI
            roi = self.getRoi(roi_id)
            if not roi or roi.mean_spectrum is None:
                QMessageBox.warning(
                    self,
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
                wavelengths, roi.mean_spectrum, f"ROI {roi.name}"
            )
            self.pixelPlotWindow.show()
            self.pixelPlotWindow.raise_()  # Bring to front

        except Exception as e:
            logger.error(f"Error plotting ROI spectrum: {e}")
            QMessageBox.warning(
                self, "Plot Error", f"Error plotting spectrum: {str(e)}"
            )

    def calculate_roi_statistics(self, roi_id):
        """Calculate detailed statistics for an ROI"""
        from varda.features.roi_statistics import calculate_roi_stats

        roi = self.getRoi(roi_id)
        if not roi:
            logger.warning(f"ROI {roi_id} not found")
            return None

        # Get the image data
        image = self.proj.getImage(self.imageIndex)
        image_data = image.raster
        wavelengths = image.metadata.wavelengths

        # Calculate statistics
        stats = calculate_roi_stats(roi, image_data, wavelengths)

        # Store statistics in the ROI for future reference
        if hasattr(roi, "statistics"):
            roi.statistics = stats.get_summary()
        else:
            # For older ROI objects, store in custom_data
            if hasattr(roi, "custom_data") and hasattr(roi.custom_data, "values"):
                roi.custom_data.values["statistics"] = stats.get_summary()

        # Signal that the ROI has been updated
        self.roiUpdated.emit(roi_id)

        return stats
