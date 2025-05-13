import logging
import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot

from core.data import ProjectContext

logger = logging.getLogger(__name__)

class ROIViewModel(QObject):
    """
    View model for ROI management.
    
    Acts as an intermediary between the ROI View and the ProjectContext/ROIManager.
    Handles business logic and data transformation for the UI.
    """
    
    # Signals
    roiAdded = pyqtSignal(str)       # Emitted when an ROI is added (passes ROI ID)
    roiRemoved = pyqtSignal(str)     # Emitted when an ROI is removed (passes ROI ID)
    roiUpdated = pyqtSignal(str)     # Emitted when an ROI is updated (passes ROI ID)
    imageChanged = pyqtSignal(int)   # Emitted when the active image changes
    
    def __init__(self, proj: ProjectContext, imageIndex: int, parent=None):
        super().__init__(parent)
        self.proj = proj
        self.imageIndex = imageIndex
        self.view = None
        self.rasterView = None
        
        # Connect to ProjectContext signals
        self._connectSignals()
        
        logger.debug(f"ROI ViewModel initialized for image {imageIndex}")
    
    def setView(self, view):
        """Set reference to the ROI View"""
        self.view = view
    
    def setRasterView(self, rasterView):
        """Set reference to the RasterView for drawing ROIs"""
        self.rasterView = rasterView
    
    def _connectSignals(self):
        """Connect to signals from the ProjectContext"""
        self.proj.sigDataChanged.connect(self._onProjectDataChanged)
    
    def updateImageIndex(self, imageIndex):
        """Update the current image index"""
        if self.imageIndex != imageIndex:
            self.imageIndex = imageIndex
            self.imageChanged.emit(imageIndex)
            logger.debug(f"ROI ViewModel image changed to {imageIndex}")
    
    def getAllRois(self):
        """Get all ROIs associated with the current image"""
        if hasattr(self.proj, 'roi_manager'):
            rois = {}
            for roi in self.proj.roi_manager.get_rois_for_image(self.imageIndex):
                rois[roi.id] = roi
            return rois
        else:
            # Fallback to legacy ROI handling
            return {roi.id: roi for roi in self.proj.getROIs(self.imageIndex)}
    
    def getROIs(self, imageIndex=None):
        """Get all ROIs for the specified image (default is current image)"""
        idx = imageIndex if imageIndex is not None else self.imageIndex
        
        if hasattr(self.proj, 'roi_manager'):
            return self.proj.get_rois_for_image(idx)
        else:
            # Legacy API
            return self.proj.getROIs(idx)
        
    def getRoi(self, roi_id):
        """Get a specific ROI by ID"""
        if hasattr(self.proj, 'roi_manager'):
            return self.proj.roi_manager.get_roi(roi_id)
        else:
            # Fallback to searching in the image's ROIs
            for roi in self.proj.getROIs(self.imageIndex):
                if hasattr(roi, 'id') and roi.id == roi_id:
                    return roi
            return None
    
    def addRoi(self, roi):
        """Add a new ROI"""
        if hasattr(self.proj, 'roi_manager'):
            # Use ROI Manager API
            roi_id = self.proj.roi_manager.add_roi(roi, [self.imageIndex])
            if roi_id:
                self.roiAdded.emit(roi_id)
            return roi_id
        else:
            # Use legacy API
            index = self.proj.addROI(self.imageIndex, roi)
            if hasattr(roi, 'id'):
                self.roiAdded.emit(roi.id)
            return roi.id if hasattr(roi, 'id') else str(index)
    
    def removeRoi(self, roi_id):
        """Remove an ROI"""
        if hasattr(self.proj, 'roi_manager'):
            # Use ROI Manager API
            result = self.proj.roi_manager.remove_roi(roi_id)
            if result:
                self.roiRemoved.emit(roi_id)
            return result
        else:
            # Use legacy API - this requires finding the index
            rois = self.proj.getROIs(self.imageIndex)
            for i, roi in enumerate(rois):
                if hasattr(roi, 'id') and roi.id == roi_id:
                    self.proj.removeROI(self.imageIndex, i)
                    self.roiRemoved.emit(roi_id)
                    return True
            return False
    
    def updateRoi(self, roi_id, **properties):
        """Update ROI properties"""
        if hasattr(self.proj, 'roi_manager'):
            # Use ROI Manager API
            result = self.proj.roi_manager.update_roi(roi_id, **properties)
            if result:
                self.roiUpdated.emit(roi_id)
            return result
        else:
            # Use legacy API
            if 'visible' in properties:
                # Special handling for visibility since it affects display
                self.updateRoiVisibility(roi_id, properties['visible'])
                
            # Update the ROI object directly
            roi = self.getRoi(roi_id)
            if roi:
                for key, value in properties.items():
                    if hasattr(roi, key):
                        setattr(roi, key, value)
                self.roiUpdated.emit(roi_id)
                return True
            return False
    
    def updateRoiVisibility(self, roi_id, visible):
        """Update ROI visibility (special case for display updates)"""
        roi = self.getRoi(roi_id)
        if roi:
            if hasattr(roi, 'visible'):
                roi.visible = visible
            self.roiUpdated.emit(roi_id)
            return True
        return False
    
    def addRoiCustomField(self, roi_id, field_name, value):
        """Add a custom field to an ROI"""
        roi = self.getRoi(roi_id)
        if roi and hasattr(roi, 'custom_data') and hasattr(roi.custom_data, 'values'):
            roi.custom_data.values[field_name] = value
            self.roiUpdated.emit(roi_id)
            return True
        return False
    
    def updateRoiCustomValue(self, roi_id, field_name, value):
        """Update a custom field value for an ROI"""
        return self.addRoiCustomField(roi_id, field_name, value)
    
    def startDrawingROI(self):
        """Start the ROI drawing process"""
        if self.rasterView:
            self.rasterView.startNewROI()
            logger.debug("Starting new ROI drawing")
        else:
            logger.warning("Cannot start ROI drawing - no RasterView available")
    
    def plotRoiSpectrum(self, roi_id):
        """Plot the spectrum of an ROI"""
        roi = self.getRoi(roi_id)
        if roi and hasattr(roi, 'mean_spectrum') and roi.mean_spectrum is not None:
            logger.debug(f"Plotting spectrum for ROI {roi_id}")
            
            # This would normally call a plotting function
            # For now, we'll delegate to the ProjectContext's plotROI method if available
            if hasattr(self.proj, 'plotROI'):
                self.proj.plotROI(roi)
            elif hasattr(self.proj, 'addPlot'):
                self.proj.addPlot(roi)
            else:
                logger.warning("No plotting function available in ProjectContext")
            
            return True
        
        logger.warning(f"Cannot plot spectrum for ROI {roi_id} - no spectral data available")
        return False
    
    def calculate_roi_statistics(self, roi_id):
        """Calculate detailed statistics for an ROI"""
        from features.roi_statistics import calculate_roi_stats
        
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
        if hasattr(roi, 'statistics'):
            roi.statistics = stats.get_summary()
        else:
            # For older ROI objects, store in custom_data
            if hasattr(roi, 'custom_data') and hasattr(roi.custom_data, 'values'):
                roi.custom_data.values['statistics'] = stats.get_summary()
        
        # Signal that the ROI has been updated
        self.roiUpdated.emit(roi_id)
        
        return stats
    
    def duplicateRoi(self, roi_id):
        """Create a duplicate of an ROI"""
        # This would create a copy of the ROI with a new ID
        # Not implemented in this version
        logger.warning("ROI duplication not implemented")
        return None
    
    def _onProjectDataChanged(self, index, changeType, changeModifier=None):
        """Handle changes in the ProjectContext"""
        # Only process events for the current image
        if index != self.imageIndex:
            return
            
        # Check if it's an ROI change
        if changeType == ProjectContext.ChangeType.ROI:
            logger.debug(f"ProjectContext ROI change: {changeModifier}")
            
            # With the new ROI manager, we can't easily determine which ROI changed
            # So we'll just emit a signal that will cause the view to refresh
            # In a more complete implementation, we'd get the specific ROI ID from the event
            
            # For now, we'll just trigger a view update
            if self.view:
                self.view.updateROITable()