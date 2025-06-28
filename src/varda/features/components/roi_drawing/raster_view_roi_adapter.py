"""
ROI Drawing Adapter for RasterView

This adapter integrates the generic ROIDrawingController with RasterView,
handling view-specific operations and coordinate transformations.
"""

import logging
from typing import Optional, Dict, Any
import numpy as np

from PyQt6.QtCore import QObject, pyqtSignal

from varda.features.components.roi_drawing.roi_drawing_controller import (
    ROIDrawingController,
    ROIDrawingConfig,
    ROIDrawingRequest,
    ROIDrawingResult,
)
from varda.core.entities.roi import ROI

logger = logging.getLogger(__name__)


class RasterViewROIAdapter(QObject):
    """
    Adapter that connects the generic ROIDrawingController to RasterView.

    This class handles:
    - View-specific operations (adding/removing ROI selectors)
    - Data model integration (creating ROI entities, saving to project)
    - Coordinate transformations if needed
    - ROI display management
    """

    # Signals for notifying about ROI operations
    roiCreated = pyqtSignal(object)  # Emits created ROI entity
    roiSelected = pyqtSignal(str)  # Emits ROI ID when selected
    roiVisibilityChanged = pyqtSignal(str, bool)  # ROI ID and visibility

    def __init__(
        self, rasterView, viewModel, config: Optional[ROIDrawingConfig] = None
    ):
        super().__init__()

        self.rasterView = rasterView
        self.viewModel = viewModel

        # Create the drawing controller
        self.drawingController = ROIDrawingController(config)

        # ROI management
        self.roiLookup = {}  # Map ROI ID to displayed selectors

        # Connect controller signals
        self._connectControllerSignals()

        # Connect to view model signals for ROI updates
        self._connectViewModelSignals()

        # Load existing ROIs
        self._loadExistingRois()

    def _connectControllerSignals(self):
        """Connect signals from the drawing controller"""
        # Drawing lifecycle
        self.drawingController.roiDrawingCompleted.connect(self._onRoiCompleted)
        self.drawingController.roiDrawingCanceled.connect(self._onRoiCanceled)

        # View requests
        self.drawingController.requestAddToView.connect(self._addSelectorToView)
        self.drawingController.requestRemoveFromView.connect(
            self._removeSelectorFromView
        )
        self.drawingController.requestShowAllROIs.connect(self._showAllRois)
        self.drawingController.requestHideAllROIs.connect(self._hideAllRois)

    def _connectViewModelSignals(self):
        """Connect to view model signals for ROI updates"""
        if not self.viewModel:
            return

        # Connect to various ROI change signals depending on view model type
        if hasattr(self.viewModel, "sigROIChanged"):
            self.viewModel.sigROIChanged.connect(self._onRoiDataChanged)

        if hasattr(self.viewModel, "roiAdded"):
            self.viewModel.roiAdded.connect(self._onRoiAdded)

        if hasattr(self.viewModel, "roiRemoved"):
            self.viewModel.roiRemoved.connect(self._onRoiRemoved)

        if hasattr(self.viewModel, "roiUpdated"):
            self.viewModel.roiUpdated.connect(self._onRoiUpdated)

    def getToolbar(self):
        """Get the ROI drawing toolbar"""
        return self.drawingController.getToolbar()

    def startDrawingRoi(self, targetItem=None):
        """Start drawing a new ROI"""
        # Use main image as default target
        if targetItem is None and hasattr(self.rasterView, "mainImage"):
            targetItem = self.rasterView.mainImage

        if not targetItem:
            logger.error("No target item available for ROI drawing")
            return False

        # Prepare metadata
        metadata = {}

        # Add image index if available
        if hasattr(self.viewModel, "imageIndex"):
            metadata["imageIndex"] = self.viewModel.imageIndex
        elif hasattr(self.viewModel, "index"):
            metadata["imageIndex"] = self.viewModel.index

        # Add geo transform if available
        try:
            if hasattr(self.viewModel, "proj"):
                image = self.viewModel.proj.getImage(metadata.get("imageIndex", 0))
                if image and hasattr(image.metadata, "transform"):
                    metadata["geoTransform"] = image.metadata.transform
        except Exception as e:
            logger.debug(f"No geo transform available: {e}")

        # Create drawing request
        request = ROIDrawingRequest(targetItem=targetItem, metadata=metadata)

        return self.drawingController.startDrawing(request)

    def cancelDrawing(self):
        """Cancel any active drawing"""
        self.drawingController.cancelDrawing()

    def setDrawingMode(self, mode):
        """Set the drawing mode"""
        self.drawingController.setDrawingMode(mode)

    def getDrawingMode(self):
        """Get the current drawing mode"""
        return self.drawingController.getDrawingMode()

    def isDrawingActive(self):
        """Check if drawing is active"""
        return self.drawingController.isDrawingActive()

    def _addSelectorToView(self, selector):
        """Add ROI selector to the raster view"""
        if hasattr(self.rasterView, "mainView"):
            self.rasterView.mainView.addItem(selector)

    def _removeSelectorFromView(self, selector):
        """Remove ROI selector from the raster view"""
        if hasattr(self.rasterView, "mainView"):
            self.rasterView.mainView.removeItem(selector)

    def _showAllRois(self):
        """Show all ROIs in the view"""
        if hasattr(self.rasterView, "draw_all_polygons"):
            self.rasterView.draw_all_polygons()

    def _hideAllRois(self):
        """Hide all ROIs in the view"""
        if hasattr(self.rasterView, "remove_polygons_from_display"):
            self.rasterView.remove_polygons_from_display()

    def _onRoiCompleted(self, result: ROIDrawingResult):
        """Handle completion of ROI drawing"""
        try:
            # Extract data from result
            points = result.points
            geoPoints = result.geoPoints
            color = result.color
            imageIndex = result.metadata.get("imageIndex", 0) if result.metadata else 0

            # Create ROI entity with image data extraction
            roi = self._createRoiEntity(points, geoPoints, color, imageIndex)

            if roi:
                # Add ROI to project/view model
                roiId = self._saveRoiToProject(roi, imageIndex)

                if roiId:
                    # Display the ROI
                    self._displayRoi(roi)

                    # Cache for lookup
                    # Note: This would need to be updated when we have proper ROI display management

                    # Emit signals
                    self.roiCreated.emit(roi)

                    # Refresh view
                    if hasattr(self.rasterView, "draw_all_polygons"):
                        self.rasterView.draw_all_polygons()

        except Exception as e:
            logger.error(f"Error handling ROI completion: {e}")

    def _onRoiCanceled(self):
        """Handle ROI drawing cancellation"""
        logger.debug("ROI drawing was canceled")

    def _createRoiEntity(self, points, geoPoints, color, imageIndex):
        """Create ROI entity with extracted image data"""
        try:
            # Get image data
            if not hasattr(self.viewModel, "proj"):
                logger.error("No project context available")
                return None

            image = self.viewModel.proj.getImage(imageIndex)
            if not image or not hasattr(image, "raster"):
                logger.error("No image raster data available")
                return None

            # Create mask from points
            from skimage.draw import polygon

            mask = np.zeros((image.raster.shape[0], image.raster.shape[1]), dtype=bool)

            # Convert points to coordinates
            if len(points) >= 2:
                yCoords = np.array(points[1], dtype=int)
                xCoords = np.array(points[0], dtype=int)

                # Clip to image bounds
                yCoords = np.clip(yCoords, 0, image.raster.shape[0] - 1)
                xCoords = np.clip(xCoords, 0, image.raster.shape[1] - 1)

                # Create polygon mask
                rr, cc = polygon(yCoords, xCoords)
                mask[rr, cc] = True

                # Extract data
                arraySlice = image.raster[mask]
                meanSpectrum = (
                    np.nanmean(arraySlice, axis=0) if arraySlice.size > 0 else None
                )

                # Create ROI entity
                roi = ROI(
                    points=np.array(points),
                    geoPoints=np.array(geoPoints) if geoPoints else None,
                    image_indices=[imageIndex],
                    color=color,
                    arraySlice=arraySlice,
                    meanSpectrum=meanSpectrum,
                )

                return roi

        except Exception as e:
            logger.error(f"Error creating ROI entity: {e}")

        return None

    def _saveRoiToProject(self, roi, imageIndex):
        """Save ROI to the project context"""
        try:
            if hasattr(self.viewModel, "addRoi"):
                # ROIViewModel interface
                return self.viewModel.addRoi(roi)

            elif hasattr(self.viewModel, "proj"):
                # RasterViewModel interface
                try:
                    return self.viewModel.proj.addROI(roi, [imageIndex])
                except Exception:
                    # Legacy interface
                    idx = self.viewModel.proj.addROI(imageIndex, roi)
                    return roi.id if hasattr(roi, "id") else str(idx)

        except Exception as e:
            logger.error(f"Error saving ROI to project: {e}")

        return None

    def _displayRoi(self, roi):
        """Display an ROI in the view (placeholder for future implementation)"""
        # This could be expanded to create display selectors for existing ROIs
        # For now, we rely on the view's existing draw_all_polygons method
        pass

    def _loadExistingRois(self):
        """Load and display existing ROIs"""
        # Trigger refresh of existing ROIs in the view
        if hasattr(self.rasterView, "draw_all_polygons"):
            self.rasterView.draw_all_polygons()

    def _onRoiDataChanged(self):
        """Handle generic ROI data changes"""
        self._loadExistingRois()

    def _onRoiAdded(self, roiId):
        """Handle ROI addition"""
        self._loadExistingRois()

    def _onRoiRemoved(self, roiId):
        """Handle ROI removal"""
        self._loadExistingRois()

    def _onRoiUpdated(self, roiId):
        """Handle ROI updates"""
        self._loadExistingRois()

    def highlightRoi(self, roiId):
        """Highlight a specific ROI"""
        # This would need to be implemented based on how ROI highlighting works
        # For now, emit the selection signal
        self.roiSelected.emit(roiId)

    def cleanup(self):
        """Clean up resources"""
        self.drawingController.cleanup()
