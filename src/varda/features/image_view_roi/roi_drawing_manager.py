"""
ROI Drawing Manager

Manages ROI drawing operations, integrates with RasterView, and handles coordinate transformations.
"""

import logging
from typing import List, Dict, Optional, Tuple
import numpy as np

from PyQt6.QtCore import Qt, QObject, pyqtSignal, QPointF, QTimer
from PyQt6.QtWidgets import QMenu, QToolBar, QLabel
from PyQt6.QtGui import QAction

from varda.gui.widgets.roi_selector import ROISelector, ROIMode
from varda.core.entities.roi import ROI

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
                rois = self.view_model.proj.getROIsForImage(self.view_model.index)
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

        self._cleanupROIDrawingState()

        # Temporarily disable navigation on main and zoom views
        self._disableNavigationForROIDrawing()

        # Enable ROI drawing on all three views
        self._enableROIDrawingOnViews()

        # Get the next color
        color = self.roi_colors[self.next_color_index]
        self.next_color_index = (self.next_color_index + 1) % len(self.roi_colors)

        # Create a new ROI selector
        self.active_roi_selector = ROISelector(color, self.draw_mode)
        self.active_roi_selector.setImageIndex(self.view_model.imageIndex)

        # Use contextImage instead of mainImage for absolute coordinates
        if imageItem is None:
            if hasattr(self.raster_view, "contextImage"):
                imageItem = self.raster_view.contextImage
            else:
                logger.error("No context image item available for ROI drawing")
                return
        self.active_roi_selector.setTargetImageItem(imageItem)

        # Try to set geo transform if available
        image = self.view_model.proj.getImage(self.view_model.imageIndex)
        if hasattr(image.metadata, "transform"):
            self.active_roi_selector.setGeoTransform(image.metadata.transform)

        # Connect signals
        self.active_roi_selector.sigDrawingComplete.connect(self.onDrawingComplete)
        self.active_roi_selector.sigDrawingCanceled.connect(self.onDrawingCanceled)

        # Add to context view instead of main view for absolute coordinates
        self.raster_view.contextView.addItem(self.active_roi_selector)
        self.active_roi_selector.draw()

        # Set instructions based on mode
        instructions = {
            ROIMode.FREEHAND: "Click and drag to draw freehand ROI on any view. Release to complete.",
            ROIMode.RECTANGLE: "Click and drag to define rectangle on any view. Release to complete.",
            ROIMode.ELLIPSE: "Click and drag to define ellipse on any view. Release to complete.",
            ROIMode.POLYGON: "Click to add points on any view. Double-click or press Enter to complete. Esc to cancel.",
        }
        self.status_label.setText(instructions[self.draw_mode])

    def _cleanupROIDrawingState(self):
        """Clean up all ROI drawing state and restore normal operation"""
        # Remove event filters from all views
        self._removeEventFiltersFromAllViews()

        # Restore navigation on main and zoom views
        self._restoreNavigationAfterROIDrawing()

        # Make sure no views think they're in ROI drawing mode
        self._clearROIDrawingFlags()

    def _disableNavigationForROIDrawing(self):
        """Temporarily disable navigation behavior on main and zoom views"""
        # Store original navigation state
        self._original_navigation_state = {}

        if hasattr(self.raster_view, "mainView"):
            # Disable navigation on main view
            self._original_navigation_state["mainView"] = getattr(
                self.raster_view.mainView, "_roi_drawing_disabled_nav", False
            )
            self.raster_view.mainView._roi_drawing_disabled_nav = True

        if hasattr(self.raster_view, "zoomView"):
            # Disable navigation on zoom view
            self._original_navigation_state["zoomView"] = getattr(
                self.raster_view.zoomView, "_roi_drawing_disabled_nav", False
            )
            self.raster_view.zoomView._roi_drawing_disabled_nav = True

    def _enableROIDrawingOnViews(self):
        """Enable ROI drawing on all three views by installing event filters"""
        # Install event filters on all view scenes to detect where user starts drawing
        if hasattr(self.raster_view, "contextView") and self.raster_view.contextView:
            scene = self.raster_view.contextView.scene()
            if scene:
                scene.installEventFilter(self)

        if hasattr(self.raster_view, "mainView") and self.raster_view.mainView:
            scene = self.raster_view.mainView.scene()
            if scene:
                scene.installEventFilter(self)

        if hasattr(self.raster_view, "zoomView") and self.raster_view.zoomView:
            scene = self.raster_view.zoomView.scene()
            if scene:
                scene.installEventFilter(self)

    def eventFilter(self, obj, event):
        """Handle mouse events to detect which view the user wants to draw on"""
        if event.type() == event.Type.GraphicsSceneMousePress:
            if event.button() == Qt.MouseButton.LeftButton:
                # Determine which view this event came from
                view_type = self._detectViewFromScene(obj)
                if view_type:
                    # Start ROI drawing on the detected view
                    self._startROIOnSpecificView(view_type, event)
                    return True

        return False

    def _detectViewFromScene(self, scene):
        """Detect which view a scene belongs to"""
        if (
            hasattr(self.raster_view, "contextView")
            and self.raster_view.contextView.scene() == scene
        ):
            return "context"
        elif (
            hasattr(self.raster_view, "mainView")
            and self.raster_view.mainView.scene() == scene
        ):
            return "main"
        elif (
            hasattr(self.raster_view, "zoomView")
            and self.raster_view.zoomView.scene() == scene
        ):
            return "zoom"
        return None

    def _startROIOnSpecificView(self, view_type, initial_event):
        """Start ROI drawing on a specific view"""
        # Remove event filters from all views since we now know which one to use
        self._removeEventFiltersFromAllViews()

        # Get the next color
        color = self.roi_colors[self.next_color_index]
        self.next_color_index = (self.next_color_index + 1) % len(self.roi_colors)

        # Create a new ROI selector with view type information
        self.active_roi_selector = ROISelector(color, self.draw_mode)
        self.active_roi_selector.setImageIndex(self.view_model.imageIndex)
        self.active_roi_selector.view_type = view_type
        # Store reference to raster view for coordinate transformations
        self.active_roi_selector.raster_view = self.raster_view

        # Set up the ROI selector for the detected view
        success = self._setupROIForView(view_type)
        if not success:
            return

        # Try to set geo transform if available
        image = self.view_model.proj.getImage(self.view_model.imageIndex)
        if hasattr(image.metadata, "transform"):
            self.active_roi_selector.setGeoTransform(image.metadata.transform)

        # Connect signals
        self.active_roi_selector.sigDrawingComplete.connect(self.onDrawingComplete)
        self.active_roi_selector.sigDrawingCanceled.connect(self.onDrawingCanceled)

        # Start drawing and process the initial mouse event
        self.active_roi_selector.draw()

        # Forward the initial mouse event to start drawing immediately
        self.active_roi_selector.eventFilter(None, initial_event)

        # Update status to show which view is being used
        view_name = view_type.capitalize()
        instructions = {
            ROIMode.FREEHAND: f"Drawing freehand ROI on {view_name} view. Release to complete.",
            ROIMode.RECTANGLE: f"Drawing rectangle on {view_name} view. Release to complete.",
            ROIMode.ELLIPSE: f"Drawing ellipse on {view_name} view. Release to complete.",
            ROIMode.POLYGON: f"Drawing polygon on {view_name} view. Double-click or Enter to complete.",
        }
        self.status_label.setText(instructions[self.draw_mode])

    def _removeEventFiltersFromAllViews(self):
        """Remove event filters from all view scenes"""
        for view_attr in ["contextView", "mainView", "zoomView"]:
            if hasattr(self.raster_view, view_attr):
                view = getattr(self.raster_view, view_attr)
                if view and view.scene():
                    view.scene().removeEventFilter(self)

    def _setupROIForView(self, view_type):
        """Set up ROI selector for the specified view type"""
        if view_type == "context":
            if hasattr(self.raster_view, "contextImage"):
                self.active_roi_selector.setTargetImageItem(
                    self.raster_view.contextImage
                )
                self.raster_view.contextView.addItem(self.active_roi_selector)
                return True

        elif view_type == "main":
            if hasattr(self.raster_view, "mainImage"):
                self.active_roi_selector.setTargetImageItem(self.raster_view.mainImage)
                self.raster_view.mainView.addItem(self.active_roi_selector)
                return True

        elif view_type == "zoom":
            if hasattr(self.raster_view, "zoomImage"):
                self.active_roi_selector.setTargetImageItem(self.raster_view.zoomImage)
                self.raster_view.zoomView.addItem(self.active_roi_selector)
                return True

        logger.error(f"Failed to set up ROI for {view_type} view")
        return False

    def onDrawingComplete(self, roi_data):
        # update onDrawingComplete call to include the roi_data
        # pass the geo_points to the freehandROI class
        # update the table to inlcude the geo_points
        # ask michael roi thresholds
        """Handle completion of ROI drawing with cleanup"""
        # Clean up event filters and restore navigation
        self._cleanupROIDrawingState()

        # Reset active selector
        self.active_roi_selector = None

        # Process the ROI data (existing logic continues...)
        if not roi_data or "points" not in roi_data:
            return

        points = roi_data["points"]
        geo_points = roi_data.get("geo_points")
        image_index = roi_data.get("image_index", self.view_model.imageIndex)
        color = roi_data.get("color", (255, 0, 0, 100))

        # Extract image data for the ROI
        array_slice = None
        try:
            # Use the view model to get the image data
            image = self.view_model.proj.getImage(image_index)
            if image and hasattr(image, "raster"):
                # Create a mask from the ROI points
                from skimage.draw import polygon

                mask = np.zeros(
                    (image.raster.shape[0], image.raster.shape[1]), dtype=bool
                )

                # Convert point arrays to row/col format
                y_coords = np.array(points[1], dtype=int)
                x_coords = np.array(points[0], dtype=int)

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

                # Create the ROI object
                roi = ROI(
                    points=np.array(points),
                    geoPoints=np.array(geo_points) if geo_points else None,
                    color=color,
                    arraySlice=array_slice,
                    meanSpectrum=mean_spectrum,
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
                        roi_id = self.view_model.proj.roi_manager.addROI(
                            roi, [image_index]
                        )

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

    def _restoreNavigationAfterROIDrawing(self):
        """Restore original navigation behavior"""
        if hasattr(self, "_original_navigation_state"):
            if (
                hasattr(self.raster_view, "mainView")
                and "mainView" in self._original_navigation_state
            ):
                self.raster_view.mainView._roi_drawing_disabled_nav = (
                    self._original_navigation_state["mainView"]
                )

            if (
                hasattr(self.raster_view, "zoomView")
                and "zoomView" in self._original_navigation_state
            ):
                self.raster_view.zoomView._roi_drawing_disabled_nav = (
                    self._original_navigation_state["zoomView"]
                )

            delattr(self, "_original_navigation_state")

    def _clearROIDrawingFlags(self):
        """Clear any ROI drawing flags on the views"""
        # Clear any drawing state flags that might be set on the views
        for view_attr in ["contextView", "mainView", "zoomView"]:
            if hasattr(self.raster_view, view_attr):
                view = getattr(self.raster_view, view_attr)
                if view:
                    # Clear any drawing state flags
                    if hasattr(view, "_roi_drawing_active"):
                        view._roi_drawing_active = False

    def onDrawingCanceled(self):
        """Handle cancellation of ROI drawing with cleanup"""
        # Clean up event filters
        self._removeEventFiltersFromAllViews()
        self._restoreNavigationAfterROIDrawing()

        # Reset active selector
        self.active_roi_selector = None
        self.status_label.setText("ROI drawing canceled")

    def displayROI(self, roi):
        """Display an existing ROI on the view"""
        if not roi or not hasattr(roi, "points") or roi.points is None:
            return

        try:
            # Create a selector to display this ROI
            selector = ROISelector(roi.color)
            selector.setImageIndex(self.view_model.imageIndex)

            # Set the points
            selector.pts = (
                [roi.points[0].tolist(), roi.points[1].tolist()]
                if isinstance(roi.points, np.ndarray)
                else roi.points
            )
            selector.updatePath()

            # Anchor the ROI to the image
            if hasattr(self.raster_view, "mainImage"):
                # Link to the main image's transform
                selector.setParentItem(self.raster_view.mainImage)

            # Add to the view
            self.raster_view.mainView.addItem(selector)

            # Cache for lookup
            self.roi_lookup[roi.id] = selector

            # Add to context view as well (scaled down version)
            if hasattr(self.raster_view, "contextView") and hasattr(
                self.raster_view, "contextImage"
            ):
                context_selector = ROISelector(roi.color)
                context_selector.pts = (
                    selector.pts.copy()
                    if hasattr(selector, "pts") and selector.pts is not None
                    else None
                )
                context_selector.updatePath()
                context_selector.setParentItem(self.raster_view.contextImage)
                self.raster_view.contextView.addItem(context_selector)

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
        # Remove the ROI selector from the view
        if roi_id in self.roi_lookup:
            selector = self.roi_lookup[roi_id]

            # Remove from views
            self.raster_view.mainView.removeItem(selector)

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
        # Try different methods to get the ROI
        if hasattr(self.view_model, "getRoi"):
            # If it's ROIViewModel
            return self.view_model.getRoi(roi_id)
        elif hasattr(self.view_model, "proj"):
            # If it's RasterViewModel, use the project context directly
            return self.view_model.proj.roi_manager.getROI(roi_id)

        return None

    def highlightROI(self, roi_id):
        """Highlight a specific ROI"""
        # Reset highlight on all ROIs
        for sel_id, selector in self.roi_lookup.items():
            # Try to get the ROI through different methods
            roi = self.getRoiById(sel_id)

            if roi and hasattr(roi, "color"):
                selector.setColor(roi.color)

        # Highlight the requested ROI
        if roi_id in self.roi_lookup:
            selector = self.roi_lookup[roi_id]

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
                selector.setColor(highlight_color)

                # Ensure the ROI is visible
                selector.setVisible(True)

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
        """Toggle visibility of a specific ROI"""
        if roi_id in self.roi_lookup:
            selector = self.roi_lookup[roi_id]
            visible = not selector.isVisible()
            selector.setVisible(visible)
            self.roiVisibilityChanged.emit(roi_id, visible)

    def updateROIPositions(self):
        """Update ROI positions when the view transform changes"""
        # This is called when the view is panned/zoomed
        # No action needed as PyQtGraph already anchors items to scene coordinates
        pass

    def getROIData(self, roi_id):
        """Get data for a specific ROI"""
        roi = self.getRoiById(roi_id)

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
                            self.view_model.proj.updateROI(
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

        # Remove all ROI selectors from views
        for roi_id, selector in self.roi_lookup.items():
            self.raster_view.mainView.removeItem(selector)

        # Clear lookup
        self.roi_lookup.clear()
