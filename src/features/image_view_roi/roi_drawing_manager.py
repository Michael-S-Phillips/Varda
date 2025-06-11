"""
ROI Drawing Manager

Manages ROI drawing operations, integrates with RasterView, and handles coordinate transformations.
"""

import logging
from typing import List, Dict, Optional, Tuple
import numpy as np

from PyQt6.QtCore import QObject, pyqtSignal, QPointF, QTimer
from PyQt6.QtWidgets import QMenu, QToolBar, QLabel
from PyQt6.QtGui import QAction

from gui.widgets.roi_selector import ROISelector, ROIMode
from core.entities.freehandROI import FreehandROI

logger = logging.getLogger(__name__)


class ROIDrawingManager(QObject):
    """
    Manages ROI drawing operations in RasterView.

    This class handles:
    - Creating and configuring ROI selectors
    - Transforming between view and image coordinates
    - Managing ROI visibility during pan/zoom
    - Providing toolbar controls for ROI operations
    """

    # Signals
    roiCreated = pyqtSignal(object)  # Emits the created ROI
    roiSelected = pyqtSignal(str)  # Emits the ROI ID when selected
    roiVisibilityChanged = pyqtSignal(str, bool)  # Emits ROI ID and visibility status

    def __init__(self, raster_view, view_model):
        super().__init__()
        self.raster_view = raster_view
        self.view_model = view_model

        # ROI drawing variables
        self.active_roi_selector = None
        self.draw_mode = ROIMode.FREEHAND
        self.roi_selectors = []  # List of active ROI selectors
        self.roi_colors = [
            (255, 0, 0, 100),  # Red
            (0, 255, 0, 100),  # Green
            (0, 0, 255, 100),  # Blue
            (255, 255, 0, 100),  # Yellow
            (255, 0, 255, 100),  # Magenta
            (0, 255, 255, 100),  # Cyan
            (255, 255, 255, 100),  # White
        ]
        self.next_color_index = 0

        # Cached ROIs for lookup by ID
        self.roi_lookup = {}  # Map ROI ID to displayed ROI selector

        # Set up status label for instructions
        self.status_label = QLabel("")

        # Initialize toolbar
        self.toolbar = None
        self.createToolbar()

        # Connect to view model signals if they exist
        if self.view_model:
            # Check if the view model has the required signals before connecting
            if hasattr(self.view_model, "roiAdded"):
                self.view_model.roiAdded.connect(self.onRoiAdded)
            if hasattr(self.view_model, "roiRemoved"):
                self.view_model.roiRemoved.connect(self.onRoiRemoved)
            if hasattr(self.view_model, "roiUpdated"):
                self.view_model.roiUpdated.connect(self.onRoiUpdated)

            # Connect to the more generic data changed signal that both view models have
            if hasattr(self.view_model, "sigROIChanged"):
                self.view_model.sigROIChanged.connect(self.onROIChanged)

        # Set up view change handlers
        self.setupViewChangeHandlers()

        # Load existing ROIs
        self.loadExistingROIs()

    def loadExistingROIs(self):
        """Load existing ROIs from the view model"""
        if not self.view_model:
            return

        # Try to get ROIs using different methods depending on view model type
        rois = []

        # If it's ROIViewModel, use getROIs
        if hasattr(self.view_model, "getROIs"):
            rois = self.view_model.getROIs()
        # If it's RasterViewModel, use proj.get_rois_for_image
        elif hasattr(self.view_model, "proj") and hasattr(self.view_model, "index"):
            try:
                rois = self.view_model.proj.get_rois_for_image(self.view_model.index)
            except Exception as e:
                logger.error(f"Error getting ROIs: {e}")

        # Display each ROI
        for roi in rois:
            self.displayROI(roi)

    def createToolbar(self):
        """Create a toolbar with ROI drawing tools"""
        self.toolbar = QToolBar("ROI Tools")

        # Drawing mode actions
        self.action_freehand = QAction("Freehand", self.toolbar)
        self.action_freehand.setCheckable(True)
        self.action_freehand.setChecked(True)
        self.action_freehand.triggered.connect(
            lambda: self.setDrawingMode(ROIMode.FREEHAND)
        )

        self.action_rectangle = QAction("Rectangle", self.toolbar)
        self.action_rectangle.setCheckable(True)
        self.action_rectangle.triggered.connect(
            lambda: self.setDrawingMode(ROIMode.RECTANGLE)
        )

        self.action_ellipse = QAction("Ellipse", self.toolbar)
        self.action_ellipse.setCheckable(True)
        self.action_ellipse.triggered.connect(
            lambda: self.setDrawingMode(ROIMode.ELLIPSE)
        )

        self.action_polygon = QAction("Polygon", self.toolbar)
        self.action_polygon.setCheckable(True)
        self.action_polygon.triggered.connect(
            lambda: self.setDrawingMode(ROIMode.POLYGON)
        )

        # Group actions for mutual exclusion
        self.draw_mode_actions = [
            self.action_freehand,
            self.action_rectangle,
            self.action_ellipse,
            self.action_polygon,
        ]

        # Add actions to toolbar
        self.toolbar.addAction(self.action_freehand)
        self.toolbar.addAction(self.action_rectangle)
        self.toolbar.addAction(self.action_ellipse)
        self.toolbar.addAction(self.action_polygon)
        self.toolbar.addSeparator()

        # Show/hide all ROIs
        self.action_show_all = QAction("Show All ROIs", self.toolbar)
        self.action_show_all.triggered.connect(self.showAllROIs)
        self.toolbar.addAction(self.action_show_all)

        self.action_hide_all = QAction("Hide All ROIs!!", self.toolbar)
        self.action_hide_all.triggered.connect(self.hideAllROIs)
        self.toolbar.addAction(self.action_hide_all)

        # Add status label
        self.toolbar.addWidget(self.status_label)

    def onROIChanged(self):
        """
        Handle changes to ROIs through the generic sigROIChanged signal.
        This method will reload all ROIs when any change is detected.
        """
        # Clear existing ROIs
        for roi_id, selector in list(self.roi_lookup.items()):
            self.raster_view.mainView.removeItem(selector)
        self.roi_lookup.clear()

        # Reload all ROIs
        self.loadExistingROIs()

    def getToolbar(self):
        """Get the ROI toolbar"""
        return self.toolbar

    def setDrawingMode(self, mode):
        """Set the current ROI drawing mode"""
        self.draw_mode = mode

        # Update action checkboxes
        for action in self.draw_mode_actions:
            action.setChecked(False)
        self.draw_mode_actions[mode].setChecked(True)

        # Update status message
        mode_names = ["Freehand", "Rectangle", "Ellipse", "Polygon"]
        self.status_label.setText(f"Drawing Mode: {mode_names[mode]}")

        # Update active ROI selector if any
        if self.active_roi_selector:
            self.active_roi_selector.setMode(mode)

    def startDrawingROI(self, imageItem=None):
        """Start drawing a new ROI"""
        # Cancel any active drawing
        if self.active_roi_selector:
            self.active_roi_selector.cancelDrawing()

        # Get the next color
        color = self.roi_colors[self.next_color_index]
        self.next_color_index = (self.next_color_index + 1) % len(self.roi_colors)

        # Create a new ROI selector
        self.active_roi_selector = ROISelector(color, self.draw_mode)
        self.active_roi_selector.setImageIndex(self.view_model.imageIndex)

        # Anchor the ROI to the image
        if imageItem is None:
            # TODO: fix all of this tight coupling to raster_view
            if hasattr(self.raster_view, "mainImage"):
                imageItem = self.raster_view.mainImage
            else:
                logger.error("No image item available for ROI drawing")
                return
        self.active_roi_selector.setTargetImageItem(imageItem)

        # Try to set geo transform if available
        image = self.view_model.proj.getImage(self.view_model.imageIndex)
        if hasattr(image.metadata, "transform"):
            self.active_roi_selector.setGeoTransform(image.metadata.transform)

        # Connect signals
        self.active_roi_selector.sigDrawingComplete.connect(self.onDrawingComplete)
        self.active_roi_selector.sigDrawingCanceled.connect(self.onDrawingCanceled)

        # Add to view
        self.raster_view.mainView.addItem(self.active_roi_selector)
        self.active_roi_selector.draw()

        # Set instructions based on mode
        instructions = {
            ROIMode.FREEHAND: "Click and drag to draw freehand ROI. Release to complete.",
            ROIMode.RECTANGLE: "Click and drag to define rectangle. Release to complete.",
            ROIMode.ELLIPSE: "Click and drag to define ellipse. Release to complete.",
            ROIMode.POLYGON: "Click to add points. Double-click or press Enter to complete. Esc to cancel.",
        }
        self.status_label.setText(instructions[self.draw_mode])

    def onDrawingComplete(self, roi_data):
        # update onDrawingComplete call to include the roi_data 
        # pass the geo_points to the freehandROI class 
        # update the table to inlcude the geo_points
        # ask michael roi thresholds
        """Handle completion of ROI drawing"""
        # Reset active selector
        self.active_roi_selector = None

        # Create FreehandROI from the points
        if not roi_data or "points" not in roi_data:
            return

        points = roi_data["points"]
        geo_points = roi_data.get("geo_points")
        print("\n")
        print(type(roi_data))
        print("\n")
        image_index = roi_data.get("image_index", self.view_model.imageIndex)
        color = roi_data.get("color", (255, 0, 0, 100))

        # Convert points from view coordinates to absolute image coordinates
        absolute_points = self._convertToAbsoluteCoordinates(points)
        if absolute_points is None:
            logger.error("Failed to convert ROI points to absolute coordinates")
            self.status_label.setText("Error: Invalid ROI coordinates")
            return

        # Extract image data for the ROI
        array_slice = None
        try:
            # Use the view model to get the image data
            image = self.view_model.proj.getImage(image_index)
            if image and hasattr(image, "raster"):
                # Create a mask from the ROI points using absolute coordinates
                from skimage.draw import polygon

                mask = np.zeros(
                    (image.raster.shape[0], image.raster.shape[1]), dtype=bool
                )

                # Use absolute coordinates for mask creation
                y_coords = np.array(absolute_points[1], dtype=int)
                x_coords = np.array(absolute_points[0], dtype=int)

                # Clip coordinates to image bounds
                y_coords = np.clip(y_coords, 0, image.raster.shape[0] - 1)
                x_coords = np.clip(x_coords, 0, image.raster.shape[1] - 1)

                # Draw the polygon mask
                rr, cc = polygon(y_coords, x_coords)
                mask[rr, cc] = True

                # Extract data for masked pixels
                array_slice = image.raster[mask]

                # Calculate mean spectrum if there are pixels in the mask
                mean_spectrum = (
                    np.nanmean(array_slice, axis=0) if array_slice.size > 0 else None
                )

                # Create the ROI object with absolute coordinates
                roi = FreehandROI(
                    points=np.array(absolute_points),
                    geo_points=np.array(geo_points) if geo_points else None,
                    image_indices=[image_index],
                    color=color,
                    array_slice=array_slice,
                    mean_spectrum=mean_spectrum,
                )

                # Add the ROI to the project context
                roi_id = None
                if self.view_model:
                    # Try different methods to add the ROI depending on view model type
                    if hasattr(self.view_model, "addRoi"):
                        # If it's ROIViewModel
                        roi_id = self.view_model.addRoi(roi)
                    elif hasattr(self.view_model, "proj") and hasattr(
                        self.view_model, "index"
                    ):
                        # If it's RasterViewModel, use the project context directly
                        try:
                            roi_id = self.view_model.proj.add_roi(roi, [image_index])
                        except Exception as e:
                            # Try legacy method as fallback
                            try:
                                idx = self.view_model.proj.addROI(image_index, roi)
                                roi_id = roi.id if hasattr(roi, "id") else str(idx)
                            except Exception as e2:
                                logger.error(f"Error adding ROI (legacy): {e2}")

                    # Display the ROI
                    if roi_id:
                        # Store the selector for this ROI
                        self.roi_lookup[roi_id] = self.displayROI(roi)

                        # Notify creation
                        self.roiCreated.emit(roi)

                        # Reset status
                        self.status_label.setText(f"ROI created successfully")
                    else:
                        self.status_label.setText(f"Error adding ROI")
        except Exception as e:
            logger.error(f"Error creating ROI: {e}")
            self.status_label.setText(f"Error creating ROI")
        self.raster_view.draw_all_polygons()

    def onDrawingCanceled(self):
        """Handle cancellation of ROI drawing"""
        self.active_roi_selector = None
        self.status_label.setText("ROI drawing canceled")

    def displayROI(self, roi):
        """Display an existing ROI on the view using absolute coordinates"""
        if not roi or not hasattr(roi, "points") or roi.points is None:
            return

        try:
            # Create a selector to display this ROI in main view
            selector = ROISelector(roi.color)
            selector.setImageIndex(self.view_model.imageIndex)

            # Convert absolute coordinates to current view coordinates for main view display
            view_points = self._convertToViewCoordinates(roi.points)
            if view_points is None:
                logger.error("Failed to convert ROI to view coordinates")
                return None

            # Set the points in view coordinates for main view
            selector.pts = view_points
            selector.updatePath()

            # Add to the main view (not anchored to image)
            self.raster_view.mainView.addItem(selector)

            # Create separate selector for context view with absolute coordinates
            context_selector = ROISelector(roi.color)
            context_selector.setImageIndex(self.view_model.imageIndex)
            
            # For context view, use absolute coordinates directly
            # Context view shows the full image, so ROI coordinates should be absolute
            if isinstance(roi.points, np.ndarray):
                context_points = [roi.points[0].tolist(), roi.points[1].tolist()]
            else:
                context_points = roi.points
                
            context_selector.pts = context_points
            context_selector.updatePath()
            
            # Anchor context ROI to the context image for proper scaling
            if hasattr(self.raster_view, 'contextImage') and self.raster_view.contextImage:
                context_selector.setParentItem(self.raster_view.contextImage)
            
            # Add to context view
            if hasattr(self.raster_view, 'contextView') and self.raster_view.contextView:
                self.raster_view.contextView.addItem(context_selector)

            # Cache both selectors for lookup
            self.roi_lookup[roi.id] = {
                'main': selector,
                'context': context_selector
            }

            return selector
        except Exception as e:
            logger.error(f"Error displaying ROI: {e}")
            return None
        
    def setupViewChangeHandlers(self):
        """Set up handlers for view transformation changes"""
        # Check if views exist before connecting
        if (
            hasattr(self.raster_view, "mainView")
            and self.raster_view.mainView is not None
        ):
            # Check if the view has the signal before connecting
            if hasattr(self.raster_view.mainView, "sigTransformChanged"):
                self.raster_view.mainView.sigTransformChanged.connect(
                    self.onViewTransformChanged
                )
            else:
                logger.warning("MainView does not have sigTransformChanged signal")

        if (
            hasattr(self.raster_view, "contextView")
            and self.raster_view.contextView is not None
        ):
            # Check if the view has the signal before connecting
            if hasattr(self.raster_view.contextView, "sigTransformChanged"):
                self.raster_view.contextView.sigTransformChanged.connect(
                    self.onViewTransformChanged
                )
            else:
                logger.warning("ContextView does not have sigTransformChanged signal")

    def onViewTransformChanged(self):
        """Handle changes to the view transformation"""
        # This is called when the view is panned/zoomed
        # If ROIs are properly anchored to the image, no additional action is needed
        pass

    def onRoiAdded(self, roi_id):
        """Handle addition of a new ROI"""
        # Get the ROI from the view model
        roi = self.view_model.getRoi(roi_id)
        if roi:
            # Display the ROI
            self.displayROI(roi)

    def onRoiRemoved(self, roi_id):
        """Handle removal of an ROI"""
        # Remove the ROI selectors from both views
        if roi_id in self.roi_lookup:
            roi_selectors = self.roi_lookup[roi_id]
            
            # Handle both old format (single selector) and new format (dict with main/context)
            if isinstance(roi_selectors, dict):
                # New format with separate selectors for main and context
                if 'main' in roi_selectors:
                    self.raster_view.mainView.removeItem(roi_selectors['main'])
                if 'context' in roi_selectors and hasattr(self.raster_view, 'contextView'):
                    self.raster_view.contextView.removeItem(roi_selectors['context'])
            else:
                # Old format with single selector
                self.raster_view.mainView.removeItem(roi_selectors)

            # Remove from lookup
            del self.roi_lookup[roi_id]

    def onRoiUpdated(self, roi_id):
        """Handle update of an ROI"""
        # Get the updated ROI from the view model
        roi = self.view_model.getRoi(roi_id)
        if roi and roi_id in self.roi_lookup:
            selector = self.roi_lookup[roi_id]

            # Update the selector
            if hasattr(roi, "color"):
                selector.setColor(roi.color)

            # Update points if they changed
            if hasattr(roi, "points") and roi.points is not None:
                selector.pts = (
                    [roi.points[0].tolist(), roi.points[1].tolist()]
                    if isinstance(roi.points, np.ndarray)
                    else roi.points
                )
                selector.updatePath()

    def getRoiById(self, roi_id):
        """Helper method to get an ROI by ID, trying different approaches."""
        roi = None

        # Try different methods to get the ROI
        if hasattr(self.view_model, "getRoi"):
            # If it's ROIViewModel
            roi = self.view_model.getRoi(roi_id)
        elif hasattr(self.view_model, "proj"):
            # If it's RasterViewModel, use the project context directly
            try:
                # Try the new API
                roi = self.view_model.proj.get_roi(roi_id)
            except (AttributeError, Exception) as e:
                # If that fails, try to find it in the list of ROIs
                try:
                    image_index = getattr(
                        self.view_model,
                        "index",
                        getattr(self.view_model, "imageIndex", 0),
                    )
                    rois = self.view_model.proj.get_rois_for_image(image_index)
                    for r in rois:
                        if hasattr(r, "id") and r.id == roi_id:
                            roi = r
                            break
                except Exception as e2:
                    logger.error(f"Error finding ROI by ID: {e2}")

        return roi

    def highlightROI(self, roi_id):
        """Highlight a specific ROI"""
        # Reset highlight on all ROIs
        for sel_id, roi_selectors in self.roi_lookup.items():
            # Get the ROI through different methods
            roi = self.getRoiById(sel_id)

            if roi and hasattr(roi, "color"):
                # Handle both old and new selector formats
                if isinstance(roi_selectors, dict):
                    if 'main' in roi_selectors:
                        roi_selectors['main'].setColor(roi.color)
                    if 'context' in roi_selectors:
                        roi_selectors['context'].setColor(roi.color)
                else:
                    roi_selectors.setColor(roi.color)

        # Highlight the requested ROI
        if roi_id in self.roi_lookup:
            roi_selectors = self.roi_lookup[roi_id]

            # Get the original color
            roi = self.getRoiById(roi_id)

            if roi and hasattr(roi, "color"):
                # Create a brighter highlight color
                r, g, b, a = roi.color
                highlight_color = (
                    min(r + 80, 255),
                    min(g + 80, 255),
                    min(b + 80, 255),
                    min(a + 50, 255),
                )
                
                # Apply highlight to both selectors
                if isinstance(roi_selectors, dict):
                    if 'main' in roi_selectors:
                        roi_selectors['main'].setColor(highlight_color)
                        roi_selectors['main'].setVisible(True)
                    if 'context' in roi_selectors:
                        roi_selectors['context'].setColor(highlight_color)
                        roi_selectors['context'].setVisible(True)
                else:
                    roi_selectors.setColor(highlight_color)
                    roi_selectors.setVisible(True)

                # Emit selection signal
                self.roiSelected.emit(roi_id)

    def showAllROIs(self):
        """Show all ROIs in the view"""
        self.raster_view.draw_all_polygons()
        self.status_label.setText("All ROIs visible")

    def hideAllROIs(self):
        """Hide all ROIs in the view"""
        self.raster_view.remove_polygons_from_display()
        self.status_label.setText("All ROIs hidden")

    def toggleROIVisibility(self, roi_id):
        """Toggle visibility of a specific ROI in both views"""
        if roi_id in self.roi_lookup:
            roi_selectors = self.roi_lookup[roi_id]
            
            # Determine current visibility from main selector
            if isinstance(roi_selectors, dict):
                current_visible = roi_selectors.get('main', roi_selectors.get('context')).isVisible()
                new_visible = not current_visible
                
                if 'main' in roi_selectors:
                    roi_selectors['main'].setVisible(new_visible)
                if 'context' in roi_selectors:
                    roi_selectors['context'].setVisible(new_visible)
            else:
                current_visible = roi_selectors.isVisible()
                new_visible = not current_visible
                roi_selectors.setVisible(new_visible)
                
            self.roiVisibilityChanged.emit(roi_id, new_visible)

    def updateROIPositions(self):
        """Update ROI positions when the view transform changes"""
        # This is called when the view is panned/zoomed
        # No action needed as PyQtGraph already anchors items to scene coordinates
        pass

    def getROIData(self, roi_id):
        """Get data for a specific ROI"""
        roi = None

        # Try to get the ROI depending on view model type
        if hasattr(self.view_model, "getRoi"):
            # If it's ROIViewModel
            roi = self.view_model.getRoi(roi_id)
        elif hasattr(self.view_model, "proj") and hasattr(self.view_model, "index"):
            # If it's RasterViewModel, use the project context directly
            try:
                roi = self.view_model.proj.get_roi(roi_id)
            except Exception as e:
                # Try to get the ROI from the list of ROIs for this image
                try:
                    rois = self.view_model.proj.get_rois_for_image(
                        self.view_model.index
                    )
                    for r in rois:
                        if hasattr(r, "id") and r.id == roi_id:
                            roi = r
                            break
                except Exception as e2:
                    logger.error(f"Error getting ROI: {e2}")

        if not roi:
            return None

        # Get array slice if not already calculated
        if not hasattr(roi, "array_slice") or roi.array_slice is None:
            try:
                # Extract image data for the ROI
                image = self.view_model.proj.getImage(self.view_model.imageIndex)
                if (
                    image
                    and hasattr(image, "raster")
                    and hasattr(roi, "points")
                    and roi.points is not None
                ):
                    # Create a mask from the ROI points
                    from skimage.draw import polygon

                    mask = np.zeros(
                        (image.raster.shape[0], image.raster.shape[1]), dtype=bool
                    )

                    # Convert point arrays to row/col format
                    points = roi.points
                    if isinstance(points, np.ndarray) and points.ndim == 2:
                        y_coords = points[1].astype(int)
                        x_coords = points[0].astype(int)
                    else:
                        y_coords = np.array(points[1], dtype=int)
                        x_coords = np.array(points[0], dtype=int)

                    # Clip coordinates to image bounds
                    y_coords = np.clip(y_coords, 0, image.raster.shape[0] - 1)
                    x_coords = np.clip(x_coords, 0, image.raster.shape[1] - 1)

                    # Draw the polygon mask
                    rr, cc = polygon(y_coords, x_coords)
                    mask[rr, cc] = True

                    # Extract data for masked pixels
                    roi.array_slice = image.raster[mask]

                    # Calculate mean spectrum
                    roi.mean_spectrum = (
                        np.nanmean(roi.array_slice, axis=0)
                        if roi.array_slice.size > 0
                        else None
                    )

                    # Update the ROI in the project context
                    try:
                        if hasattr(self.view_model, "updateRoi"):
                            self.view_model.updateRoi(
                                roi_id,
                                array_slice=roi.array_slice,
                                mean_spectrum=roi.mean_spectrum,
                            )
                        elif hasattr(self.view_model, "proj"):
                            self.view_model.proj.update_roi(
                                roi_id,
                                array_slice=roi.array_slice,
                                mean_spectrum=roi.mean_spectrum,
                            )
                    except Exception as e:
                        logger.error(f"Error updating ROI: {e}")
            except Exception as e:
                logger.error(f"Error extracting ROI data: {e}")

        return roi

    def cleanupROIs(self):
        """Clean up all ROI resources"""
        # Cancel any active drawing
        if self.active_roi_selector:
            self.active_roi_selector.cancelDrawing()
            self.active_roi_selector = None

        # Remove all ROI selectors from both views
        for roi_id, roi_selectors in self.roi_lookup.items():
            try:
                if isinstance(roi_selectors, dict):
                    if 'main' in roi_selectors:
                        self.raster_view.mainView.removeItem(roi_selectors['main'])
                    if 'context' in roi_selectors and hasattr(self.raster_view, 'contextView'):
                        self.raster_view.contextView.removeItem(roi_selectors['context'])
                else:
                    self.raster_view.mainView.removeItem(roi_selectors)
            except Exception as e:
                logger.debug(f"Error removing ROI selector during cleanup: {e}")

        # Clear lookup
        self.roi_lookup.clear()

    def refreshROIDisplayPositions(self):
        """Refresh the display positions of all ROIs when views change."""
        try:
            # Remove existing ROI displays
            for roi_id, selector in list(self.roi_lookup.items()):
                self.raster_view.mainView.removeItem(selector)
                if hasattr(self.raster_view, 'contextView'):
                    # Remove from context view too (though context ROIs should be persistent)
                    pass
            
            # Clear the lookup and reload all ROIs with updated positions
            self.roi_lookup.clear()
            self.loadExistingROIs()
            
        except Exception as e:
            logger.error(f"Error refreshing ROI positions: {e}")

    def _convertToAbsoluteCoordinates(self, view_points):
        """Convert points from current view coordinates to absolute image coordinates.
        
        Args:
            view_points: Points in current view coordinate system [x_coords, y_coords]
            
        Returns:
            Absolute image coordinates [x_coords, y_coords] or None if conversion fails
        """
        try:
            if not hasattr(self.raster_view, 'contextROI') or not hasattr(self.raster_view, 'mainROI'):
                logger.warning("ROI references not available for coordinate conversion")
                return view_points  # Fallback to original points
                
            # Get the current position offsets from the ROI system
            context_pos = self.raster_view.contextROI.pos() if self.raster_view.contextROI else (0, 0)
            main_pos = self.raster_view.mainROI.pos() if self.raster_view.mainROI else (0, 0)
            
            # Convert view coordinates to absolute image coordinates
            x_coords = []
            y_coords = []
            
            for i in range(len(view_points[0])):
                # Add the offsets to get absolute coordinates
                abs_x = view_points[0][i] + main_pos.x() + context_pos.x()
                abs_y = view_points[1][i] + main_pos.y() + context_pos.y()
                
                x_coords.append(abs_x)
                y_coords.append(abs_y)
                
            return [x_coords, y_coords]
            
        except Exception as e:
            logger.error(f"Error converting coordinates: {e}")
            return None
        
    def _convertToViewCoordinates(self, absolute_points):
        """Convert absolute image coordinates to current view coordinates.
        
        Args:
            absolute_points: Points in absolute image coordinates [x_coords, y_coords]
            
        Returns:
            View coordinates [x_coords, y_coords] or None if conversion fails
        """
        try:
            if not hasattr(self.raster_view, 'contextROI') or not hasattr(self.raster_view, 'mainROI'):
                return absolute_points  # Fallback
                
            # Get the current position offsets
            context_pos = self.raster_view.contextROI.pos() if self.raster_view.contextROI else (0, 0)
            main_pos = self.raster_view.mainROI.pos() if self.raster_view.mainROI else (0, 0)
            
            # Convert absolute coordinates to view coordinates
            x_coords = []
            y_coords = []
            
            for i in range(len(absolute_points[0])):
                # Subtract the offsets to get view coordinates
                view_x = absolute_points[0][i] - main_pos.x() - context_pos.x()
                view_y = absolute_points[1][i] - main_pos.y() - context_pos.y()
                
                x_coords.append(view_x)
                y_coords.append(view_y)
                
            return [x_coords, y_coords]
            
        except Exception as e:
            logger.error(f"Error converting to view coordinates: {e}")
            return None

    def _convertToContextCoordinates(self, absolute_points):
        """Convert absolute image coordinates to context view coordinates.
        
        Args:
            absolute_points: Points in absolute image coordinates [x_coords, y_coords]
            
        Returns:
            Context view coordinates [x_coords, y_coords] or None if conversion fails
        """
        try:
            # For context view, points should be in absolute image coordinates
            # but we may need to scale them if the context view is scaled
            return [list(absolute_points[0]), list(absolute_points[1])]
            
        except Exception as e:
            logger.error(f"Error converting to context coordinates: {e}")
            return None
