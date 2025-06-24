import logging
import numpy as np
import rasterio
from typing import Dict, Any, Optional, Tuple

from PyQt6 import QtCore, QtWidgets
from PyQt6.QtCore import QEvent, pyqtSignal, QPointF, QRectF, Qt
from PyQt6.QtGui import QPainter, QColor, QPolygonF
from PyQt6.QtWidgets import QWidget
import pyqtgraph as pg

from scipy.spatial import ConvexHull
from skimage.draw import polygon

from varda.features.shared.selection_controls import StretchSelector, BandSelector
from varda.features.image_view_roi.roi_drawing_manager import ROIDrawingManager
from varda.gui.widgets.roi_selector import ROISelector
from varda.core.entities.freehandROI import FreehandROI
from .raster_viewmodel import RasterViewModel

logger = logging.getLogger(__name__)


# custom view box classes for different views
class NavigableViewBox(pg.ViewBox):
    """Base ViewBox class with custom navigation behavior"""

    def __init__(self, raster_view, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.raster_view = raster_view
        self._drag_start_pos = None
        self._drag_start_scene_pos = None
        self._is_navigating = False
        self._initial_roi_pos = None
        self._roi_drawing_disabled_nav = False

    def mouseDragEvent(self, ev, axis=None):
        """Override mouse drag to implement image navigation instead of view panning"""
        if getattr(self, '_roi_drawing_disabled_nav', False):
            # Let the event pass through to ROI drawing instead of handling navigation
            super().mouseDragEvent(ev, axis)
            return
        
        if ev.button() == QtCore.Qt.MouseButton.LeftButton:
            if ev.isStart():
                self._drag_start_pos = ev.pos()
                self._drag_start_scene_pos = self.mapToView(ev.pos())
                self._is_navigating = True
                self._store_initial_roi_pos()
                ev.accept()
                return
            elif ev.isFinish():
                if self._is_navigating:
                    self._handle_navigation_end(ev)
                self._reset_drag_state()
                ev.accept()
                return
            elif self._is_navigating:
                self._handle_navigation_drag(ev)
                ev.accept()
                return

        # For other buttons or when not navigating, use default behavior
        super().mouseDragEvent(ev, axis)

    def _reset_drag_state(self):
        """Reset drag state variables"""
        self._is_navigating = False
        self._drag_start_pos = None
        self._drag_start_scene_pos = None
        self._initial_roi_pos = None

    def _store_initial_roi_pos(self):
        """Store initial ROI position - to be implemented by subclasses"""
        pass

    def _handle_navigation_drag(self, ev):
        """Handle ongoing navigation drag - to be implemented by subclasses"""
        pass

    def _handle_navigation_end(self, ev):
        """Handle end of navigation drag - to be implemented by subclasses"""
        pass


class MainViewBox(NavigableViewBox):
    """Custom ViewBox for main view - drags move the contextROI"""

    def _store_initial_roi_pos(self):
        """Store initial contextROI position"""
        if hasattr(self.raster_view, "contextROI") and self.raster_view.contextROI:
            pos = self.raster_view.contextROI.pos()
            self._initial_roi_pos = [pos[0], pos[1]]

    def _handle_navigation_drag(self, ev):
        """Move contextROI based on drag in main view"""
        if (
            not hasattr(self.raster_view, "contextROI")
            or not self.raster_view.contextROI
        ):
            return

        if self._drag_start_scene_pos is None or self._initial_roi_pos is None:
            return

        # Get current mouse position in scene coordinates
        current_scene_pos = self.mapToView(ev.pos())

        # Calculate total delta from start of drag
        delta_x = current_scene_pos.x() - self._drag_start_scene_pos.x()
        delta_y = current_scene_pos.y() - self._drag_start_scene_pos.y()

        # Apply delta to initial ROI position (inverted for intuitive panning)
        new_x = self._initial_roi_pos[0] - delta_x
        new_y = self._initial_roi_pos[1] - delta_y

        # Get contextROI size for boundary checking
        context_roi = self.raster_view.contextROI
        roi_size = context_roi.size()

        # Get image bounds to constrain movement
        if hasattr(self.raster_view, "contextImage") and self.raster_view.contextImage:
            img_bounds = self.raster_view.contextImage.boundingRect()
            # Constrain to image boundaries
            new_x = max(img_bounds.left(), min(new_x, img_bounds.right() - roi_size[0]))
            new_y = max(img_bounds.top(), min(new_y, img_bounds.bottom() - roi_size[1]))

        # Update contextROI position
        context_roi.setPos([new_x, new_y], update=True)


class ZoomViewBox(NavigableViewBox):
    """Custom ViewBox for zoom view - drags move the mainROI"""

    def _store_initial_roi_pos(self):
        """Store initial mainROI position"""
        if hasattr(self.raster_view, "mainROI") and self.raster_view.mainROI:
            pos = self.raster_view.mainROI.pos()
            self._initial_roi_pos = [pos[0], pos[1]]

    def _handle_navigation_drag(self, ev):
        """Move mainROI based on drag in zoom view"""
        if not hasattr(self.raster_view, "mainROI") or not self.raster_view.mainROI:
            return

        if self._drag_start_scene_pos is None or self._initial_roi_pos is None:
            return

        # Get current mouse position in scene coordinates
        current_scene_pos = self.mapToView(ev.pos())

        # Calculate total delta from start of drag
        delta_x = current_scene_pos.x() - self._drag_start_scene_pos.x()
        delta_y = current_scene_pos.y() - self._drag_start_scene_pos.y()

        # Apply delta to initial ROI position (inverted for intuitive panning)
        new_x = self._initial_roi_pos[0] - delta_x
        new_y = self._initial_roi_pos[1] - delta_y

        # Get mainROI size for boundary checking
        main_roi = self.raster_view.mainROI
        roi_size = main_roi.size()

        # Get main image bounds to constrain movement
        if hasattr(self.raster_view, "mainImage") and self.raster_view.mainImage:
            img_bounds = self.raster_view.mainImage.boundingRect()
            # Constrain to image boundaries
            new_x = max(img_bounds.left(), min(new_x, img_bounds.right() - roi_size[0]))
            new_y = max(img_bounds.top(), min(new_y, img_bounds.bottom() - roi_size[1]))

        # Update mainROI position
        main_roi.setPos([new_x, new_y], update=True)


class ContextViewBox(pg.ViewBox):
    """Custom ViewBox for context view - keeps standard behavior for now"""

    def __init__(self, raster_view, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.raster_view = raster_view


class RasterView(QWidget):
    """Main widget for displaying and interacting with raster images."""

    sigImageClicked = pyqtSignal(int, int)
    sigNavigationChanged = pyqtSignal(dict)  # Emitted when view navigation changes
    sigROIChanged = pyqtSignal(str)  # Emitted when ROI is modified
    sigCrosshairChanged = pyqtSignal(int, int, int, int)  # zoom_x, zoom_y, abs_x, abs_y

    def __init__(self, viewmodel: RasterViewModel, parent=None):
        super().__init__(parent=parent)
        self.viewModel = viewmodel

        # Initialize image items and views
        self.mainImage = None
        self.contextImage = None
        self.zoomImage = None

        self.mainView = None
        self.contextView = None
        self.zoomView = None

        self.contextROI = None
        self.mainROI = None

        self.freehandROIs = []

        self.roiColors = [
            (255, 0, 0, 100),  # Red
            (0, 255, 0, 100),  # Green
            (0, 0, 255, 100),  # Blue
            (255, 255, 0, 100),  # Yellow
            (255, 0, 255, 100),  # Magenta
            (0, 255, 255, 100),  # Cyan
        ]
        self.colorIndex = 0
        self.highlighted_roi_index = None

        self.roiItems = {"main": [], "context": []}

        # Dual image mode support
        self._dual_mode_active = False
        self._is_overlay_secondary = False
        self._overlay_opacity = 1.0
        self._sync_navigation = True
        self._sync_rois = True
        self._navigation_sync_in_progress = False

        # Track view state for synchronization with debouncing
        self._last_view_state = {}
        self._sync_timer = None  # For debouncing navigation updates

        # Initialize the UI
        self._initUI()
        self._initROIS()
        self._connectSignals()

        # Log initial image information
        self._logImageInfo()

        # Draw any existing ROIs
        self._refresh_polygons()

    def _logImageInfo(self):
        """Log information about the loaded image."""
        try:
            image = self.viewModel.proj.getImage(self.viewModel.index)
            logger.debug(f"Image shape: {image.raster.shape}")
            logger.debug(
                f"Metadata wavelength shape: {image.metadata.wavelengths.shape}"
            )
            logger.debug(f"First few wavelengths: {image.metadata.wavelengths[:5]}")
            logger.debug(
                f"Wavelength range: {image.metadata.wavelengths.min():.2f} - {image.metadata.wavelengths.max():.2f} nm"
            )
        except Exception as e:
            logger.error(f"Error logging image info: {str(e)}")

    def _initUI(self):
        """Initialize the user interface components."""
        # Initialize Image Items
        self.mainImage = self._initImageItem()
        self.contextImage = self._initImageItem()
        self.zoomImage = self._initImageItem()
        # Initialize ROI drawing manager
        self.roi_drawing_manager = ROIDrawingManager(self, self.viewModel)

        # Initialize view boxes with custom navigation behavior
        self.mainView = self._initMainViewBox("Main View", self.mainImage)
        self.contextView = self._initContextViewBox("Context View", self.contextImage)
        self.zoomView = self._initZoomViewBox("Zoom View", self.zoomImage)

        # Initialize with consistent stretch values
        self.current_stretch_levels = None

        # Add crosshairs to zoom view
        self.crosshair_v = pg.InfiniteLine(angle=90, movable=False, pen="r")
        self.crosshair_h = pg.InfiniteLine(angle=0, movable=False, pen="r")
        self.zoomView.addItem(self.crosshair_v)
        self.zoomView.addItem(self.crosshair_h)

        # Connect zoom image click handler
        self.zoomImage.mouseClickEvent = self.zoomImageClicked

        # Build the layout
        self._buildLayout()

    def _buildLayout(self):
        """Build the widget layout."""
        # Create graphics views
        mainGraphicsView = pg.GraphicsView()
        mainGraphicsView.setCentralItem(self.mainView)

        contextGraphicsView = pg.GraphicsView()
        contextGraphicsView.setCentralItem(self.contextView)

        zoomGraphicsView = pg.GraphicsView()
        zoomGraphicsView.setCentralItem(self.zoomView)

        # Create splitters
        verticalSplitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        verticalSplitter.addWidget(contextGraphicsView)
        verticalSplitter.addWidget(zoomGraphicsView)

        horizontalSplitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        horizontalSplitter.addWidget(mainGraphicsView)
        horizontalSplitter.addWidget(verticalSplitter)

        first_roi = ROISelector(None)
        first_roi.setImageIndex(self.viewModel.index)
        self.freehandROIs.append(first_roi)
        mainGraphicsView.addItem(self.freehandROIs[0])

        # Create main layout
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(horizontalSplitter)
        self.setLayout(layout)

        # Add ROI toolbar if available
        if hasattr(self, "roi_drawing_manager"):
            roi_toolbar = self.roi_drawing_manager.getToolbar()
            if roi_toolbar:
                layout.addWidget(roi_toolbar)

    def zoomImageClicked(self, event):
        """Handle clicks on the zoom image."""
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            # Get click position in image coordinates
            pos = self.zoomImage.mapFromScene(event.scenePos())
            x, y = int(pos.x()), int(pos.y())

            # Convert to absolute image coordinates
            final_x, final_y = self._zoomCoordsToAbsolute(x, y)

            # Update crosshair on current view
            self._updateCrosshair(x, y)

            # Emit click signal for local processing
            self.sigImageClicked.emit(final_x, final_y)

            # Sync crosshair to other view if in dual mode
            if self._dual_mode_active and hasattr(self, "sigNavigationChanged"):
                crosshair_state = {
                    "type": "crosshair_update",
                    "zoom_coords": [x, y],
                    "abs_coords": [final_x, final_y],
                }
                self.sigNavigationChanged.emit(crosshair_state)

            # test geospatial info
            if self.viewModel.getImage().metadata.geoReferencer is not None:
                (
                    lon,
                    lat,
                ) = self.viewModel.getImage().metadata.geoReferencer.pixelToCoordinates(
                    final_x, final_y
                )
                noCRS_lon, noCRS_lat = rasterio.transform.xy(
                    self.viewModel.getImage().metadata.geoReferencer.transform,
                    final_x,
                    final_y,
                )
                (
                    new_x,
                    new_y,
                ) = self.viewModel.getImage().metadata.geoReferencer.coordinatesToPixel(
                    lon, lat
                )
                logger.debug(
                    f"Zoom Image clicked. \n   Pixel Coords: {final_x}, {final_y} \n   Geospatial Coords: {lon}, {lat}\n   Geospatial before applying CRS: {noCRS_lon}, {noCRS_lat}\n   Converted Geospatial Coords back to Pixel Coords: {new_x}, {new_y}"
                )
            else:
                logger.debug("Image does not contain geospatial info!")
        event.accept()

    def _zoomCoordsToAbsolute(self, xZoom, yZoom):
        """Transforms coordinates from the zoom view space into absolute image space"""
        final_x = int(self.contextROI.pos().x() + self.mainROI.pos().x() + xZoom)
        final_y = int(self.contextROI.pos().y() + self.mainROI.pos().y() + yZoom)

        image_size = self.viewModel.proj.getImage(self.viewModel.index).raster.shape
        if final_x in range(0, image_size[1]) and final_y in range(0, image_size[0]):
            return final_x, final_y
        else:
            raise IndexError(f"Selected coordinates are invalid: {final_x}, {final_y}")

    def _updateCrosshair(self, x, y):
        self.crosshair_v.setPos(x)
        self.crosshair_h.setPos(y)

    def _connectSignals(self):
        """Connect ROI signals."""
        if self.contextROI:
            self.contextROI.sigRegionChanged.connect(self._updateViews)
        if self.mainROI:
            self.mainROI.sigRegionChanged.connect(self._updateViews)

        # Make sure stretch changes are properly handled
        self.viewModel.sigStretchChanged.connect(self._onStretchChanged)
        self.viewModel.sigBandChanged.connect(self._onBandChanged)
        self.viewModel.sigROIChanged.connect(self._refresh_polygons)

        # Add logging to better understand what's happening
        logger.debug("Connected signals in RasterView")

    def _initROIS(self):
        """Initialize Region of Interest elements."""
        self.clearROIs()

        # Initialize context ROI
        self._updateImageItem(self.contextImage, self.viewModel.getRasterFromBand())
        self.contextROI = self._getDefaultROI(self.contextImage)
        self.contextView.addItem(self.contextROI)

        # Initialize main ROI
        self._updateMainView()
        self.mainROI = self._getDefaultROI(self.mainImage)
        self.mainView.addItem(self.mainROI)

        # Update zoom view
        self._updateZoomView()

    def clearROIs(self):
        """Clear existing ROIs."""
        if self.contextROI is not None:
            self.contextView.removeItem(self.contextROI)
        if self.mainROI is not None:
            self.mainView.removeItem(self.mainROI)

    def _updateViews(self):
        """Update all views."""
        self._updateContextView()
        self._updateImageItem(self.contextImage, self.viewModel.getRasterFromBand())
        self._updateMainView()
        self._updateZoomView()
        self.draw_all_polygons()

    def _updateContextView(self):
        """Update the context view based on the current image."""

        self.current_stretch_levels = self.viewModel.getSelectedStretch().toList()
        logger.debug(
            f"Updating context image with new levels: {self.current_stretch_levels}"
        )
        rasterData = self.viewModel.getRasterFromBand()
        self.contextImage.setImage(rasterData, levels=self.current_stretch_levels)

        # Update the context image with the current raster data
        self._updateImageItem(self.contextImage, self.viewModel.getRasterFromBand())

    def _updateMainView(self):
        """Update the main view based on context ROI."""
        if self.contextROI is None:
            return

        self._makeROISquare(self.contextROI)

        self.mainImage.setRegion(
            self.contextImage.image, self.contextROI, self.contextImage
        )

        if self.mainROI is not None:
            self.mainROI.maxBounds = self.mainImage.boundingRect()

    def _updateZoomView(self):
        """Update the zoom view based on main ROI."""
        if self.mainROI is None:
            return

        self._makeROISquare(self.mainROI)

        self.zoomImage.setRegion(self.mainImage.image, self.mainROI, self.mainImage)

    def _updateImageItem(self, imageItem, rasterData):
        """Update an image item with new raster data."""
        # If it's the context image, get fresh stretch values
        if imageItem == self.contextImage:
            self.current_stretch_levels = self.viewModel.getSelectedStretch().toList()
            logger.debug(
                f"Updating context image with new levels: {self.current_stretch_levels}"
            )

        # Always use the current stretch levels for consistency
        if self.current_stretch_levels is None:
            self.current_stretch_levels = self.viewModel.getSelectedStretch().toList()
            logger.debug(f"Initializing stretch levels: {self.current_stretch_levels}")
        imageItem.setImage(rasterData, levels=self.current_stretch_levels)

    def selectStretch(self, stretchIndex):
        """Select a new stretch to apply to the image."""
        self.viewModel.selectStretch(stretchIndex)

    def _onStretchChanged(self):
        """Handle stretch changes."""
        # Get the current stretch values directly from the view model
        stretch = self.viewModel.getSelectedStretch()
        levels = stretch.toList()

        # Update our cached stretch levels and log
        self.current_stretch_levels = levels
        logger.debug(
            f"RasterView received stretch change: {levels}, type: {type(levels[0][0])}"
        )

        # Update the image items with the new levels - explicitly convert to ensure correct types
        # Note: It's important that we pass the exact same levels object to all images
        self.mainImage.setLevels(levels)
        self.contextImage.setLevels(levels)
        self.zoomImage.setLevels(levels)

        # Force a redraw
        self.mainView.update()
        self.contextView.update()
        self.zoomView.update()

        logger.debug(f"After update, contextImage levels: {self.contextImage.levels}")

    def _onBandChanged(self):
        """Handle band changes."""
        self._updateViews()

    def _connect_dual_mode_signals(self):
        """Connect signals for dual image mode support"""
        try:
            # Only connect if not already connected and in dual mode
            if not self._dual_mode_active:
                return

            # Connect to contextROI changes (red box in context view)
            if hasattr(self, "contextROI") and self.contextROI:
                try:
                    self.contextROI.sigRegionChanged.disconnect(
                        self._on_context_roi_navigation_changed
                    )
                except:
                    pass
                self.contextROI.sigRegionChanged.connect(
                    self._on_context_roi_navigation_changed
                )
                logger.debug(
                    "Connected contextROI.sigRegionChanged for navigation sync"
                )

            # Connect to mainROI changes (red box in main view)
            if hasattr(self, "mainROI") and self.mainROI:
                try:
                    self.mainROI.sigRegionChanged.disconnect(
                        self._on_main_roi_navigation_changed
                    )
                except:
                    pass
                self.mainROI.sigRegionChanged.connect(
                    self._on_main_roi_navigation_changed
                )
                logger.debug("Connected mainROI.sigRegionChanged for navigation sync")

            # Connect ROI change signals for dual image synchronization
            if hasattr(self.viewModel, "sigDataChanged"):
                try:
                    self.viewModel.sigDataChanged.disconnect(self._on_roi_data_changed)
                except:
                    pass
                self.viewModel.sigDataChanged.connect(self._on_roi_data_changed)

        except Exception as e:
            logger.error(f"Error connecting dual mode signals: {e}")

    def _on_main_roi_navigation_changed(self):
        """Handle mainROI position changes for navigation sync"""
        if (
            self._navigation_sync_in_progress
            or not self._dual_mode_active
            or not self._sync_navigation
        ):
            return

        try:
            logger.debug("mainROI position changed - triggering navigation sync")

            if hasattr(self, "mainROI") and self.mainROI:
                pos = self.mainROI.pos()
                size = self.mainROI.size()

                roi_state = {
                    "type": "main_roi",
                    "pos": [pos.x(), pos.y()],
                    "size": [size.x(), size.y()],
                }

                logger.debug(
                    f"mainROI changed: pos=({pos.x():.6f}, {pos.y():.6f}), size=({size.x():.6f}, {size.y():.6f})"
                )

                if hasattr(self, "sigNavigationChanged"):
                    self.sigNavigationChanged.emit(roi_state)
                    logger.debug("Emitted mainROI navigation change")

        except Exception as e:
            logger.error(f"Error handling mainROI navigation change: {e}")

    def _on_context_roi_navigation_changed(self):
        """Handle contextROI position changes for navigation sync"""
        if (
            self._navigation_sync_in_progress
            or not self._dual_mode_active
            or not self._sync_navigation
        ):
            return

        try:
            logger.debug("contextROI position changed - triggering navigation sync")

            if hasattr(self, "contextROI") and self.contextROI:
                pos = self.contextROI.pos()
                size = self.contextROI.size()

                roi_state = {
                    "type": "context_roi",
                    "pos": [
                        pos.x(),
                        pos.y(),
                    ],
                    "size": [
                        size.x(),
                        size.y(),
                    ],
                }

                logger.debug(
                    f"contextROI changed: pos=({pos.x():.6f}, {pos.y():.6f}), size=({size.x():.6f}, {size.y():.6f})"
                )

                if hasattr(self, "sigNavigationChanged"):
                    self.sigNavigationChanged.emit(roi_state)
                    logger.debug("Emitted contextROI navigation change")

        except Exception as e:
            logger.error(f"Error handling contextROI navigation change: {e}")

    def _on_context_roi_changed(self):
        """Handle context ROI changes for navigation sync"""
        if self._navigation_sync_in_progress or not self._dual_mode_active:
            return

        try:
            # Extract view state from context ROI
            if hasattr(self, "mainROI") and self.mainROI:
                pos = self.mainROI.pos()
                size = self.mainROI.size()

                view_state = {
                    "x_range": [pos[0], pos[0] + size[0]],
                    "y_range": [pos[1], pos[1] + size[1]],
                    "center_x": pos[0] + size[0] / 2,
                    "center_y": pos[1] + size[1] / 2,
                    "zoom_x": size[0],
                    "zoom_y": size[1],
                }

                if view_state != self._last_view_state:
                    self._last_view_state = view_state.copy()
                    self.sigNavigationChanged.emit(view_state)

        except Exception as e:
            logger.error(f"Error handling context ROI change: {e}")

    def _on_navigation_changed(self, view_box, range_info=None):
        """Handle navigation changes for dual image synchronization with debouncing"""
        if (
            self._navigation_sync_in_progress
            or not self._dual_mode_active
            or not self._sync_navigation
        ):
            return

        try:
            # Use a timer to debounce rapid navigation changes
            if self._sync_timer is not None:
                self._sync_timer.stop()
                self._sync_timer.deleteLater()

            from PyQt6.QtCore import QTimer

            self._sync_timer = QTimer()
            self._sync_timer.setSingleShot(True)
            self._sync_timer.timeout.connect(self._emit_navigation_change)
            self._sync_timer.start(50)  # 50ms debounce

        except Exception as e:
            logger.error(f"Error handling navigation change: {e}")

    def _emit_navigation_change(self):
        """Emit navigation change after debounce delay"""
        try:
            if self._navigation_sync_in_progress or not self._dual_mode_active:
                return

            # Extract current view state from the main view
            if not self.mainView:
                return

            # Get the current view range
            view_range = self.mainView.viewRange()
            if not view_range or len(view_range) != 2:
                return

            x_range, y_range = view_range

            # Calculate center and zoom level
            center_x = (x_range[0] + x_range[1]) / 2
            center_y = (y_range[0] + y_range[1]) / 2
            zoom_x = x_range[1] - x_range[0]
            zoom_y = y_range[1] - y_range[0]

            # Create view state dictionary
            view_state = {
                "x_range": x_range,
                "y_range": y_range,
                "center_x": center_x,
                "center_y": center_y,
                "zoom_x": zoom_x,
                "zoom_y": zoom_y,
            }

            # Only emit if the view state has actually changed
            if view_state != self._last_view_state:
                self._last_view_state = view_state.copy()

                # Emit the navigation changed signal
                if hasattr(self, "sigNavigationChanged"):
                    self.sigNavigationChanged.emit(view_state)
                    logger.debug(
                        f"Emitted navigation change: center=({center_x:.1f}, {center_y:.1f}), zoom=({zoom_x:.1f}, {zoom_y:.1f})"
                    )
                else:
                    logger.warning("sigNavigationChanged signal not available")

        except Exception as e:
            logger.error(f"Error emitting navigation change: {e}")
        finally:
            # Clean up the timer
            if hasattr(self, "_sync_timer") and self._sync_timer:
                self._sync_timer.deleteLater()
                self._sync_timer = None

    def _is_significantly_different(self, new_state, old_state, threshold=1.0):
        """Check if the view state has changed significantly to avoid micro-updates"""
        if not old_state:
            return True

        try:
            # Check if ranges differ by more than threshold pixels
            new_x = new_state.get("x_range", [0, 0])
            new_y = new_state.get("y_range", [0, 0])
            old_x = old_state.get("x_range", [0, 0])
            old_y = old_state.get("y_range", [0, 0])

            x_diff = abs(new_x[0] - old_x[0]) + abs(new_x[1] - old_x[1])
            y_diff = abs(new_y[0] - old_y[0]) + abs(new_y[1] - old_y[1])

            return x_diff > threshold or y_diff > threshold

        except:
            return True

    def _extract_view_state(self) -> Dict[str, Any]:
        """Extract current view state for synchronization"""
        view_state = {}

        if self.mainView:
            try:
                # Get the current view range from the main view
                view_range = self.mainView.viewRange()
                if view_range and len(view_range) >= 2:
                    x_range = view_range[0]
                    y_range = view_range[1]

                    # Ensure ranges are valid
                    if (
                        len(x_range) >= 2
                        and len(y_range) >= 2
                        and not any(
                            v is None or not isinstance(v, (int, float))
                            for v in x_range + y_range
                        )
                    ):

                        # Convert to float to ensure JSON serialization compatibility
                        x_range = [float(x_range[0]), float(x_range[1])]
                        y_range = [float(y_range[0]), float(y_range[1])]

                        view_state.update(
                            {
                                "x_range": x_range,
                                "y_range": y_range,
                                "center_x": (x_range[0] + x_range[1]) / 2,
                                "center_y": (y_range[0] + y_range[1]) / 2,
                                "zoom_x": x_range[1] - x_range[0],
                                "zoom_y": y_range[1] - y_range[0],
                            }
                        )

                        logger.debug(
                            f"Extracted view state: x_range={x_range}, y_range={y_range}"
                        )
                    else:
                        logger.warning(
                            f"Invalid view range values: x_range={x_range}, y_range={y_range}"
                        )
                else:
                    logger.warning(f"Invalid view range structure: {view_range}")

            except Exception as e:
                logger.error(f"Error extracting view state: {e}")
        else:
            logger.warning("mainView is None, cannot extract view state")

        return view_state

    def _on_roi_data_changed(self, *args):
        """Handle ROI data changes for dual image synchronization"""
        if self._dual_mode_active and self._sync_rois:
            # Extract ROI ID from args if available
            roi_id = None
            if len(args) >= 2 and hasattr(args[1], "value"):
                if args[1].value == "roi":  # Assuming ChangeType.ROI
                    roi_id = "latest"  # Could be more specific with actual ROI ID

            if roi_id:
                self.sigROIChanged.emit(roi_id)

    # Methods for dual image mode support
    def set_dual_mode(self, active: bool, is_overlay_secondary: bool = False):
        """
        Set dual image mode state.

        Args:
            active: Whether dual mode is active
            is_overlay_secondary: Whether this view is the secondary (overlay) view
        """
        logger.debug(
            f"Setting dual mode: active={active}, overlay_secondary={is_overlay_secondary}"
        )

        self._dual_mode_active = active
        self._is_overlay_secondary = is_overlay_secondary

        if active:
            # Configure for dual mode
            if is_overlay_secondary:
                self._setup_overlay_mode()
            else:
                self._setup_primary_mode()

            self._connect_dual_mode_signals()

        else:
            # Reset to normal mode
            self._reset_normal_mode()

    def _on_transform_changed(self, *args):
        """Alternative handler for transform changes (backup method)"""
        if self._navigation_sync_in_progress or not self._dual_mode_active:
            return

        logger.debug("Transform changed - triggering navigation sync")
        # Trigger the same navigation change as range changed
        self._on_navigation_changed(None, None)

    def _setup_overlay_mode(self):
        """Configure view for overlay mode (as secondary image)"""
        # Adjust opacity for overlay
        if self.mainImage:
            self.mainImage.setOpacity(self._overlay_opacity)
        if self.contextImage:
            self.contextImage.setOpacity(self._overlay_opacity)
        if self.zoomImage:
            self.zoomImage.setOpacity(self._overlay_opacity)

        # Set overlay-specific styling
        self.setStyleSheet(
            """
            QWidget {
                background-color: transparent;
            }
        """
        )

        # Ensure proper stacking order for overlay
        self.raise_()

        logger.debug("RasterView configured for overlay mode")

    def set_overlay_blend_mode(self, blend_mode: str = "normal"):
        """
        Set the blend mode for overlay (future enhancement).

        Args:
            blend_mode: Blend mode ("normal", "multiply", "screen", etc.)
        """
        # This is a placeholder for future blend mode implementation
        # Would require custom painting or graphics effects
        logger.debug(f"Blend mode set to: {blend_mode} (placeholder)")

    def enable_overlay_interaction(self, enabled: bool = True):
        """
        Enable or disable interaction with overlay view.

        Args:
            enabled: Whether overlay should respond to mouse/keyboard input
        """
        if self._is_overlay_secondary:
            # Control whether overlay intercepts mouse events
            if enabled:
                self.setAttribute(
                    Qt.WidgetAttribute.WA_TransparentForMouseEvents, False
                )
            else:
                self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def _setup_primary_mode(self):
        """Configure view for primary mode in dual setup"""
        # Ensure full opacity for primary
        if self.mainImage:
            self.mainImage.setOpacity(1.0)

        logger.debug("RasterView configured for primary mode")

    def _reset_normal_mode(self):
        """Reset view to normal (single image) mode"""
        # Disconnect navigation signals to prevent interference
        try:
            if hasattr(self.mainView, "sigRangeChanged"):
                self.mainView.sigRangeChanged.disconnect(self._on_navigation_changed)
        except:
            pass

        # Reset opacity
        if self.mainImage:
            self.mainImage.setOpacity(1.0)
        if self.contextImage:
            self.contextImage.setOpacity(1.0)
        if self.zoomImage:
            self.zoomImage.setOpacity(1.0)

        # Reset styling
        self.setStyleSheet("")

        self._dual_mode_active = False
        self._is_overlay_secondary = False
        logger.debug("RasterView reset to normal mode")

    def get_overlay_opacity(self) -> float:
        """Get the current overlay opacity"""
        return self._overlay_opacity

    def set_overlay_opacity(self, opacity: float):
        """
        Set overlay opacity for this view.

        Args:
            opacity: Opacity value between 0.0 and 1.0
        """
        self._overlay_opacity = max(0.0, min(1.0, opacity))

        if self._is_overlay_secondary:
            # Apply opacity to the main image item
            if self.mainImage:
                self.mainImage.setOpacity(self._overlay_opacity)

            # Also apply to context and zoom images for consistency
            if self.contextImage:
                self.contextImage.setOpacity(self._overlay_opacity)
            if self.zoomImage:
                self.zoomImage.setOpacity(self._overlay_opacity)

            logger.debug(f"Set overlay opacity to {self._overlay_opacity}")

    def set_sync_settings(self, sync_navigation: bool = True, sync_rois: bool = True):
        """
        Configure synchronization settings.

        Args:
            sync_navigation: Whether to sync navigation (pan/zoom)
            sync_rois: Whether to sync ROI changes
        """
        self._sync_navigation = sync_navigation
        self._sync_rois = sync_rois

    def sync_navigation_from_other(self, view_state: Dict[str, Any]):
        """
        Synchronize navigation state from another view.

        Args:
            view_state: Dictionary containing ROI state from another RasterView
        """
        if not self._dual_mode_active or not self._sync_navigation:
            logger.debug(
                "Sync blocked: dual_mode_active={}, sync_navigation={}".format(
                    self._dual_mode_active, self._sync_navigation
                )
            )
            return

        # Prevent recursive sync
        self._navigation_sync_in_progress = True

        try:
            roi_type = view_state.get("type")
            logger.debug(f"Syncing {roi_type}: {view_state}")

            if roi_type == "crosshair_update":
                # Handle crosshair synchronization
                abs_coords = view_state.get("abs_coords", [0, 0])
                zoom_coords = self._absoluteToZoomCoords(abs_coords[0], abs_coords[1])
                if zoom_coords:
                    self._updateCrosshair(zoom_coords[0], zoom_coords[1])
                    logger.debug(f"Synced crosshair to zoom coords {zoom_coords}")

            elif (
                roi_type == "context_roi"
                and hasattr(self, "contextROI")
                and self.contextROI
            ):
                # Sync contextROI position with improved precision
                pos_data = view_state.get("pos", [0.0, 0.0])
                size_data = view_state.get("size", [100.0, 100.0])

                # Validate coordinate data
                if self._validate_coordinates(pos_data, size_data):
                    from PyQt6.QtCore import QPointF

                    new_pos = QPointF(float(pos_data[0]), float(pos_data[1]))
                    new_size = QPointF(float(size_data[0]), float(size_data[1]))

                    # Check if position change is significant enough to warrant update
                    current_pos = self.contextROI.pos()
                    current_size = self.contextROI.size()

                    if self._is_coordinate_change_significant(
                        current_pos, new_pos, current_size, new_size
                    ):
                        # Temporarily disconnect to prevent recursive sync
                        try:
                            self.contextROI.sigRegionChanged.disconnect(
                                self._on_context_roi_navigation_changed
                            )
                        except:
                            pass

                        # Apply bounds checking before setting position
                        bounded_pos, bounded_size = self._apply_bounds_checking(
                            new_pos, new_size, "context"
                        )

                        # Apply the new position and size with precision
                        self.contextROI.setPos(bounded_pos)
                        self.contextROI.setSize(bounded_size)

                        # Reconnect the signal
                        self.contextROI.sigRegionChanged.connect(
                            self._on_context_roi_navigation_changed
                        )

                        logger.debug(
                            f"Synced contextROI to pos=({bounded_pos.x():.6f}, {bounded_pos.y():.6f}), "
                            f"size=({bounded_size.x():.6f}, {bounded_size.y():.6f})"
                        )
                    else:
                        logger.debug(
                            "Skipped contextROI sync - change below significance threshold"
                        )
                else:
                    logger.warning(
                        f"Invalid coordinates for contextROI sync: pos={pos_data}, size={size_data}"
                    )

            elif roi_type == "main_roi" and hasattr(self, "mainROI") and self.mainROI:
                # Sync mainROI position with improved precision
                pos_data = view_state.get("pos", [0.0, 0.0])
                size_data = view_state.get("size", [50.0, 50.0])

                # Validate coordinate data
                if self._validate_coordinates(pos_data, size_data):
                    from PyQt6.QtCore import QPointF

                    new_pos = QPointF(float(pos_data[0]), float(pos_data[1]))
                    new_size = QPointF(float(size_data[0]), float(size_data[1]))

                    # Check if position change is significant enough to warrant update
                    current_pos = self.mainROI.pos()
                    current_size = self.mainROI.size()

                    if self._is_coordinate_change_significant(
                        current_pos, new_pos, current_size, new_size
                    ):
                        # Temporarily disconnect to prevent recursive sync
                        try:
                            self.mainROI.sigRegionChanged.disconnect(
                                self._on_main_roi_navigation_changed
                            )
                        except:
                            pass

                        # Apply bounds checking before setting position
                        bounded_pos, bounded_size = self._apply_bounds_checking(
                            new_pos, new_size, "main"
                        )

                        # Apply the new position and size with precision
                        self.mainROI.setPos(bounded_pos)
                        self.mainROI.setSize(bounded_size)

                        # Reconnect the signal
                        self.mainROI.sigRegionChanged.connect(
                            self._on_main_roi_navigation_changed
                        )

                        logger.debug(
                            f"Synced mainROI to pos=({bounded_pos.x():.6f}, {bounded_pos.y():.6f}), "
                            f"size=({bounded_size.x():.6f}, {bounded_size.y():.6f})"
                        )
                    else:
                        logger.debug(
                            "Skipped mainROI sync - change below significance threshold"
                        )
                else:
                    logger.warning(
                        f"Invalid coordinates for mainROI sync: pos={pos_data}, size={size_data}"
                    )

            # Only update views for ROI changes, not crosshair updates
            if roi_type != "crosshair_update":
                self._updateViews()
                self.update()

                # Process events to ensure updates are applied immediately
                from PyQt6.QtCore import QCoreApplication

                QCoreApplication.processEvents()

            logger.debug("Navigation sync applied successfully")

        except Exception as e:
            logger.error(f"Error syncing navigation: {e}")
            import traceback

            logger.error(traceback.format_exc())

        finally:
            # Reset sync flag immediately after sync completion
            self._navigation_sync_in_progress = False

    def _validate_coordinates(self, pos_data, size_data, min_size=0.5) -> bool:
        """Validate coordinate data for ROI sync operations with enhanced checks"""
        try:
            # Check if coordinates are numeric and not None
            if not pos_data or not size_data:
                return False

            if len(pos_data) != 2 or len(size_data) != 2:
                return False

            if not all(isinstance(x, (int, float)) for x in pos_data + size_data):
                return False

            # Check for NaN or infinite values
            if any(not np.isfinite(x) for x in pos_data + size_data):
                return False

            # Check minimum size requirements (allow smaller minimum for precision)
            if size_data[0] < min_size or size_data[1] < min_size:
                return False

            # Size should always be positive
            if size_data[0] <= 0 or size_data[1] <= 0:
                return False

            # Check for reasonable maximum values to prevent overflow
            max_coord = 1e6  # 1 million pixels should be reasonable maximum
            if any(abs(x) > max_coord for x in pos_data + size_data):
                return False

            return True

        except (TypeError, IndexError, AttributeError):
            return False

    def _is_coordinate_change_significant(
        self, current_pos, new_pos, current_size, new_size, threshold=0.1
    ) -> bool:
        """Check if coordinate change is significant enough to warrant an update"""
        return True
        # try:
        #     # Calculate total displacement
        #     pos_delta = abs(new_pos.x() - current_pos.x()) + abs(new_pos.y() - current_pos.y())
        #     size_delta = abs(new_size.x() - current_size.x()) + abs(new_size.y() - current_size.y())

        #     # Return True if change exceeds threshold
        #     return pos_delta > threshold or size_delta > threshold

        # except (AttributeError, TypeError):
        #     # If we can't calculate, assume change is significant
        #     return True

    def _apply_bounds_checking(self, pos, size, roi_type="main"):
        """Apply bounds checking to ensure ROI stays within valid image bounds"""
        try:
            from PyQt6.QtCore import QPointF

            bounded_pos = QPointF(pos.x(), pos.y())
            bounded_size = QPointF(size.x(), size.y())

            # Get image bounds based on ROI type
            if roi_type == "context" and self.contextImage:
                image_bounds = self.contextImage.boundingRect()
            elif roi_type == "main" and self.mainImage:
                image_bounds = self.mainImage.boundingRect()
            else:
                # No bounds available, return original values
                return bounded_pos, bounded_size

            # Ensure position is within image bounds
            bounded_pos.setX(
                max(
                    image_bounds.left(),
                    min(bounded_pos.x(), image_bounds.right() - bounded_size.x()),
                )
            )
            bounded_pos.setY(
                max(
                    image_bounds.top(),
                    min(bounded_pos.y(), image_bounds.bottom() - bounded_size.y()),
                )
            )

            # Ensure size doesn't exceed image bounds
            max_width = image_bounds.width() - bounded_pos.x()
            max_height = image_bounds.height() - bounded_pos.y()

            bounded_size.setX(min(bounded_size.x(), max_width))
            bounded_size.setY(min(bounded_size.y(), max_height))

            # Ensure minimum size
            bounded_size.setX(max(bounded_size.x(), 1.0))
            bounded_size.setY(max(bounded_size.y(), 1.0))

            return bounded_pos, bounded_size

        except Exception as e:
            logger.warning(f"Error in bounds checking: {e}")
            return pos, size

    def debug_view_state(self):
        """Debug method to check view state"""
        logger.debug(f"=== RasterView Debug State ===")
        logger.debug(f"Widget visible: {self.isVisible()}")
        logger.debug(f"Widget enabled: {self.isEnabled()}")
        logger.debug(f"Widget size: {self.size()}")
        logger.debug(f"Dual mode active: {self._dual_mode_active}")
        logger.debug(f"Is overlay secondary: {self._is_overlay_secondary}")
        logger.debug(f"Sync navigation: {self._sync_navigation}")

        if self.mainView:
            logger.debug(f"MainView visible: {self.mainView.isVisible()}")
            logger.debug(f"MainView range: {self.mainView.viewRange()}")
            logger.debug(f"MainView enabled: {self.mainView.isEnabled()}")
        else:
            logger.debug("MainView is None")

        logger.debug(f"===============================")

    def sync_roi_from_other(self, roi_id: str):
        """
        Synchronize ROI from another view.

        Args:
            roi_id: ID of the ROI to synchronize
        """
        if not self._dual_mode_active or not self._sync_rois:
            return

        try:
            # Get the ROI data from the project context
            # This would depend on how ROIs are stored and accessed
            logger.debug(f"Syncing ROI {roi_id} from other view")

            # Refresh ROI display to show synchronized ROI
            self._refresh_polygons()

        except Exception as e:
            logger.error(f"Error syncing ROI {roi_id}: {e}")

    def set_blink_visibility(self, visible: bool):
        """
        Set visibility for blink mode.

        Args:
            visible: Whether this view should be visible in blink mode
        """
        self.setVisible(visible)

        # Also control the visibility of the image items
        if self.mainImage:
            self.mainImage.setVisible(visible)
        if self.contextImage:
            self.contextImage.setVisible(visible)

    def get_view_state(self) -> Dict[str, Any]:
        """Get current view state for synchronization"""
        return self._extract_view_state()

    def is_dual_mode_active(self) -> bool:
        """Check if dual mode is currently active"""
        return self._dual_mode_active

    def is_overlay_secondary(self) -> bool:
        """Check if this view is configured as overlay secondary"""
        return self._is_overlay_secondary

    def _sync_crosshair_to_other_view(self, zoom_x, zoom_y, abs_x, abs_y):
        """
        Sync crosshair position to the other view in dual image mode.

        Args:
            zoom_x, zoom_y: Crosshair position in zoom view coordinates
            abs_x, abs_y: Crosshair position in absolute image coordinates
        """
        try:
            if hasattr(self, "sigCrosshairChanged"):
                self.sigCrosshairChanged.emit(zoom_x, zoom_y, abs_x, abs_y)
                logger.debug(
                    f"Emitted crosshair sync: zoom=({zoom_x}, {zoom_y}), abs=({abs_x}, {abs_y})"
                )
        except Exception as e:
            logger.error(f"Error syncing crosshair: {e}")

    def sync_crosshair_from_other(self, abs_x, abs_y):
        """
        Update crosshair position based on sync from another view.

        Args:
            abs_x, abs_y: Absolute image coordinates for crosshair position
        """
        if not self._dual_mode_active:
            return

        try:
            # Convert absolute coordinates to zoom view coordinates
            zoom_coords = self._absoluteToZoomCoords(abs_x, abs_y)
            if zoom_coords:
                zoom_x, zoom_y = zoom_coords
                self._updateCrosshair(zoom_x, zoom_y)
                logger.debug(f"Synced crosshair to zoom coords ({zoom_x}, {zoom_y})")
        except Exception as e:
            logger.error(f"Error syncing crosshair from other view: {e}")

    def _absoluteToZoomCoords(self, abs_x, abs_y):
        """
        Convert absolute image coordinates to zoom view coordinates.

        Args:
            abs_x, abs_y: Absolute image coordinates

        Returns:
            tuple: (zoom_x, zoom_y) coordinates or None if invalid
        """
        try:
            if not (
                hasattr(self, "contextROI")
                and self.contextROI
                and hasattr(self, "mainROI")
                and self.mainROI
            ):
                return None

            # Calculate zoom coordinates by reversing the transformation from _zoomCoordsToAbsolute
            zoom_x = abs_x - self.contextROI.pos().x() - self.mainROI.pos().x()
            zoom_y = abs_y - self.contextROI.pos().y() - self.mainROI.pos().y()

            return int(zoom_x), int(zoom_y)

        except Exception as e:
            logger.error(f"Error converting absolute to zoom coordinates: {e}")
            return None

    # def startDrawingROI(self):
    #     """Start the ROI drawing process."""
    #     if self.freehandROI:
    #         self.freehandROI.draw()

    def startNewROI(self):
        """Create and start a new ROI using the drawing manager (enhanced for dual mode)"""
        # Call existing method
        if hasattr(self, "roi_drawing_manager") and self.roi_drawing_manager:
            self.roi_drawing_manager.startDrawingROI(self.mainImage)
        else:
            # Fallback to existing implementation
            super().startNewROI() if hasattr(super(), "startNewROI") else None

    def highlightROI(self, roi_index):
        """Highlight a specific ROI by index (enhanced for dual mode)"""
        # Call existing method
        self.highlighted_roi_index = roi_index
        self._refresh_polygons()

        # Emit signal for dual mode synchronization
        if self._dual_mode_active:
            self.sigROIChanged.emit(f"highlight_{roi_index}")

    def remove_polygons_from_display(self):
        """Remove all polygons from the display"""
        for item in self.roiItems["main"]:

            self.mainView.removeItem(item)

        for item in self.roiItems["context"]:
            self.contextView.removeItem(item)
        print("\n")
        for item in self.mainView.allChildren():
            if isinstance(item, ROISelector):
                self.mainView.removeItem(item)
                print(item)
        print("\n")

    def _refresh_polygons(self):
        """Redraw all ROI polygons"""
        print("here")
        self.remove_polygons_from_display()
        self.draw_all_polygons()

    # Update draw_all_polygons to support highlighting
    def draw_all_polygons(self):
        """Draw all ROIs with optional highlighting for the selected one"""
        # Get ROIs from the project
        self.remove_polygons_from_display()

        rois = self.viewModel.proj.get_rois_for_image(self.viewModel.index)
        if not rois:
            return

        for i, roi in enumerate(rois):
            # Get color and points from the ROI
            color = roi.color if hasattr(roi, "color") else (255, 0, 0, 128)
            highlighted = (
                hasattr(self, "highlighted_roi_index")
                and self.highlighted_roi_index == i
            )

            # Get points - handle different ROI formats
            if hasattr(roi, "points") and roi.points is not None:
                # FreehandROI style - points is [x_coords, y_coords]
                if isinstance(roi.points, list) and len(roi.points) == 2:
                    points = [(x, y) for x, y in zip(roi.points[0], roi.points[1])]
                else:
                    points = roi.points

                # Create a polygon with the points
                polygonForContext = pg.Qt.QtGui.QPolygonF()
                polygonForMain = pg.Qt.QtGui.QPolygonF()

                for x, y in zip(*points):
                    # add points to context polygon
                    polygonForContext.append(pg.Qt.QtCore.QPointF(x, y))
                    logger.debug(
                        "Adding point to polygon for context: ({}, {})".format(x, y)
                    )

                    # add points to main polygon, clamping to bounds
                    mainImageCoords = self.mainImage.getLocalCoords(QPointF(x, y))
                    polygonForMain.append(pg.Qt.QtCore.QPointF(mainImageCoords))
                    logger.debug(
                        "Adding point to polygon for main: ({}, {})".format(
                            mainImageCoords.x(), mainImageCoords.y()
                        )
                    )

                # This clips the polygon to the bounds of the main image
                polygonForMain = polygonForMain.intersected(
                    QPolygonF(self.mainImage.boundingRect())
                )

                # Create a polygon item with the color
                from PyQt6.QtGui import QPen, QBrush

                pen_width = 2
                if highlighted:
                    pen = QPen(QColor(255, 255, 0))  # Yellow for highlight
                    pen.setWidth(3)
                else:
                    pen = QPen(QColor(color[0], color[1], color[2]))
                    pen.setWidth(pen_width)

                brush = QBrush(
                    QColor(
                        color[0],
                        color[1],
                        color[2],
                        color[3] if len(color) >= 4 else 128,
                    )
                )
                contextPolygonItem = pg.Qt.QtWidgets.QGraphicsPolygonItem(
                    polygonForContext
                )
                contextPolygonItem.setPen(pen)
                contextPolygonItem.setBrush(brush)
                self.contextView.addItem(contextPolygonItem)

                mainPolygonItem = pg.Qt.QtWidgets.QGraphicsPolygonItem(polygonForMain)
                mainPolygonItem.setPen(pen)
                mainPolygonItem.setBrush(brush)
                self.mainView.addItem(mainPolygonItem)

                # Store references to remove them later
                self.roiItems["main"].append(mainPolygonItem)
                self.roiItems["context"].append(contextPolygonItem)

    def closeEvent(self, event):
        """Clean up resources when the view is closed (enhanced)"""
        # Reset dual mode
        if self._dual_mode_active:
            self.set_dual_mode(False)

        # Clean up ROI resources (existing code)
        if hasattr(self, "roi_drawing_manager"):
            self.roi_drawing_manager.cleanupROIs()

        super().closeEvent(event)

    @staticmethod
    def _initImageItem():
        """Initialize a new image item."""
        return RasterView.ImageRegionItem(
            axisOrder="row-major", autoLevels=False, levels=(0, 1)
        )

    def _initMainViewBox(self, name, imageItem):
        """Initialize the main view box with custom navigation behavior."""
        viewBox = MainViewBox(
            raster_view=self, name=name, lockAspect=True, invertY=True
        )
        viewBox.addItem(imageItem)
        # Enable mouse interaction for panning and zooming
        viewBox.setMouseEnabled(x=True, y=True)
        return viewBox

    def _initContextViewBox(self, name, imageItem):
        """Initialize the context view box."""
        viewBox = ContextViewBox(
            raster_view=self, name=name, lockAspect=True, invertY=True
        )
        viewBox.addItem(imageItem)
        # Enable mouse interaction for panning and zooming
        viewBox.setMouseEnabled(x=True, y=True)
        return viewBox

    def _initZoomViewBox(self, name, imageItem):
        """Initialize the zoom view box with custom navigation behavior."""
        viewBox = ZoomViewBox(
            raster_view=self, name=name, lockAspect=True, invertY=True
        )
        viewBox.addItem(imageItem)
        # Enable mouse interaction for panning and zooming
        viewBox.setMouseEnabled(x=True, y=True)
        return viewBox

    @staticmethod
    def _initViewBox(name, imageItem):
        """Legacy method - kept for compatibility but should use specific methods above."""
        viewBox = pg.ViewBox(name=name, lockAspect=True, invertY=True)
        viewBox.addItem(imageItem)
        # Enable mouse interaction for panning and zooming
        viewBox.setMouseEnabled(x=True, y=True)
        return viewBox

    @staticmethod
    def _getDefaultROI(imageItem):
        """Get default ROI for an image item."""
        imgRect = imageItem.boundingRect()
        center = imageItem.mapToParent(imgRect.center())
        startSize = (imgRect.width() / 4, imgRect.height() / 4)
        return pg.RectROI(center, startSize, pen=(0, 9), maxBounds=imgRect)

    @staticmethod
    def _makeROISquare(roi):
        """Make an ROI square shaped."""
        size = roi.size()
        minDim = min(size.x(), size.y())
        roi.setSize([minDim, minDim], update=False)
        handle = roi.handles[0]["item"]
        handle.setPos(minDim, minDim)

    class ImageRegionItem(pg.ImageItem):
        """
        Custom ImageItem that supports only displaying a region of the image,
        with a convenience method to get the absolute image coordinates.
        """

        def __init__(self, image=None, **kwargs):
            super().__init__(image=image, **kwargs)
            self.region = None

        def setRegion(
            self, image: pg.ImageItem, region: pg.ROI, sourceImageItem: pg.ImageItem
        ):
            """Set the region of interest for zooming."""
            self.region = region
            rasterData = self.region.getArrayRegion(image, sourceImageItem)
            self.setImage(rasterData, autoLevels=False)

        def getAbsoluteCoords(self, point: QPointF):
            """Convert local zoomed coordinates to absolute image coordinates."""
            if self.region is None:
                return point
            # Calculate absolute coordinates based on the region
            abs_x = int(self.region.pos().x() + point.x())
            abs_y = int(self.region.pos().y() + point.y())
            return QPointF(abs_x, abs_y)

        def getLocalCoords(self, point: QPointF):
            """Convert absolute image coordinates to local zoomed coordinates."""
            if self.region is None:
                return point
            # Calculate local coordinates based on the region
            local_x = int(point.x() - self.region.pos().x())
            local_y = int(point.y() - self.region.pos().y())
            return QPointF(local_x, local_y)

        def getOffset(self):
            """Get the offset of the image item."""
            if self.region is None:
                return QtCore.QPointF(0, 0)
            return self.region.pos()
