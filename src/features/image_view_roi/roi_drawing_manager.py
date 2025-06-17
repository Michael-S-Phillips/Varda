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
                roi = FreehandROI(
                    points=np.array(points),
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

        # Remove all ROI selectors from views
        for roi_id, selector in self.roi_lookup.items():
            self.raster_view.mainView.removeItem(selector)

        # Clear lookup
        self.roi_lookup.clear()
