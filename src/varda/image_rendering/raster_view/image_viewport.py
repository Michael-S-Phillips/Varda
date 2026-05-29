from PyQt6.QtCore import pyqtSignal, QPointF, QRectF
from PyQt6.QtWidgets import QWidget, QVBoxLayout
import pyqtgraph as pg
import numpy as np

from varda import log
from varda.common.entities import VardaRaster
from varda.image_rendering import ImageRenderer
from varda.image_rendering.raster_view.navigable_view_box import NavigableViewBox
from varda.image_rendering.raster_view.viewport_tools.viewport_tool import (
    ViewportTool,
)
from varda.image_rendering.raster_view.protocols import Viewport
from varda.image_rendering.raster_view.image_region_item import (
    VardaImageItem,
)


class ViewportMeta(type(QWidget), type(Viewport)):
    pass


class ImageViewport(QWidget, Viewport, metaclass=ViewportMeta):
    """
    Generic image viewer: holds a single Viewbox with an ImageRegionItem, and helper methods.

    Navigation lives in the ViewBox (`NavigableViewBox`). By default the viewport navigates
    itself (native pan/zoom). With `disableSelfNavigation()` it instead re-emits drag/scroll
    as high-level gestures (`sigPanned`, `sigZoomed`) for an external controller to handle —
    used when something else (e.g. RegionController) drives what the viewport shows.
    """

    sigImageChanged = pyqtSignal()

    # Navigation gestures, forwarded from the ViewBox. Emitted only while self-navigation
    # is disabled. Positions are in view (data) coordinates.
    sigPanStarted = pyqtSignal(QPointF)  # press position
    sigPanned = pyqtSignal(QPointF, QPointF)  # (current position, start position)
    sigPanEnded = pyqtSignal()
    sigZoomed = pyqtSignal(float, QPointF)  # (scaleFactor, anchorFraction)
    # Emitted when a user gesture pans/zooms this viewport's own view (self-navigation on).
    # Mirrors pyqtgraph's viewBox.sigRangeChangedManually but without its mask argument.
    sigViewRangeChangedManually = pyqtSignal()

    def __init__(self, imageRenderer: ImageRenderer, parent=None):
        super().__init__(parent)
        self.selfUpdating = True

        self._imageRenderer = imageRenderer
        self._imageItem: VardaImageItem = VardaImageItem(self._imageRenderer)

        self._overlayImageRenderer: ImageRenderer | None = None
        self._overlayImageItem: VardaImageItem | None = None

        self._vb = NavigableViewBox(lockAspect=True, invertY=True)
        self._vb.addItem(self._imageItem)
        self._gv = pg.GraphicsView()
        self._gv.setCentralItem(self._vb)
        layout = QVBoxLayout(self)
        layout.addWidget(self._gv)
        self.setLayout(layout)

        # Forward navigation signals so consumers depend on the viewport, not the ViewBox.
        self._vb.sigPanStarted.connect(self.sigPanStarted)
        self._vb.sigPanned.connect(self.sigPanned)
        self._vb.sigPanEnded.connect(self.sigPanEnded)
        self._vb.sigZoomed.connect(self.sigZoomed)
        self._vb.sigRangeChangedManually.connect(self._onViewBoxRangeChangedManually)

        self._imageItem.sigImageChanged.connect(self.sigImageChanged)
        self._imageRenderer.sigShouldRefresh.connect(self.autoRefresh)

    def overlayImage(self, overlayImageRenderer: ImageRenderer):
        """Overlay an image on top of the current image.
        It's possible that we may want to support multiple overlay images in the future, or overlay with different blending modes,
        but for now we'll just support one.
        """
        self._overlayImageRenderer = overlayImageRenderer
        if self._overlayImageItem is not None:
            log.info("An image is already overlayed. Replacing it with the new one.")
            self.removeOverlayImage()
        self._overlayImageItem = VardaImageItem(overlayImageRenderer)
        self._vb.addItem(self._overlayImageItem)

        overlayImageRenderer.sigShouldRefresh.connect(self.autoRefresh)

    def removeOverlayImage(self):
        """Remove the overlay image."""
        if self._overlayImageItem is not None:
            self._vb.removeItem(self._overlayImageItem)
            self._overlayImageItem = None
            self._overlayImageRenderer.sigShouldRefresh.disconnect(self.autoRefresh)
            self._overlayImageRenderer = None
        else:
            log.warning("No overlay image to remove.")

    def disableSelfUpdating(self):
        """Disable self-updating of the image item."""
        self.selfUpdating = False

    def enableSelfUpdating(self):
        """Enable self-updating of the image item."""
        self.selfUpdating = True

    def autoRefresh(self):
        if self.selfUpdating:
            self.refresh()

    def refresh(self):
        """Refresh the image display with current settings."""
        self._imageItem.refresh()
        if self._overlayImageItem is not None:
            self._overlayImageItem.refresh()

    # --- Navigation ---

    def enableSelfNavigation(self):
        """Let mouse gestures pan/zoom this viewport's own view range (the default)."""
        self._vb.setSelfNavigating(True)

    def disableSelfNavigation(self):
        """Stop this viewport from panning/zooming itself in response to gestures.

        Gestures are still detected and emitted as signals; the viewport just doesn't
        move its own view. Used when an external controller (e.g. RegionController)
        drives what the viewport shows.
        """
        self._vb.setSelfNavigating(False)

    def _onViewBoxRangeChangedManually(self, *args):
        self.sigViewRangeChangedManually.emit()

    # --- View / range helpers ---

    def mapToView(self, point: QPointF) -> QPointF:
        """Map a point from ViewBox-local coordinates to view (data) coordinates."""
        return self._vb.mapToView(point)

    def viewRect(self) -> QRectF:
        """The currently displayed range, in view (data) coordinates."""
        return self._vb.viewRect()

    def setViewRange(self, rect: QRectF, padding: float = 0):
        """Set the displayed range, in view (data) coordinates."""
        self._vb.setRange(rect=rect, padding=padding)

    # --- Coordinate conversion ---

    def localToImage(self, point):
        """Convert viewport-local coordinates to full-image pixel coordinates."""
        return self._imageItem.localToImage(point)

    def imageToLocal(self, point):
        """Convert full-image pixel coordinates to viewport-local coordinates."""
        return self._imageItem.imageToLocal(point)

    def imageBounds(self) -> QRectF:
        """The bounding rectangle of the displayed image, in viewport-local coordinates."""
        return self._imageItem.boundingRect()

    def pixelToLocalCoords(self, pixelCoords: np.ndarray) -> np.ndarray:
        """
        Convert full-image pixel coordinates to the viewport's local coordinates
        (since a viewport may be showing only an inner region of the image).
        """
        if not self.imageItem.isShowingRegion:
            return pixelCoords
        pointsList = [(float(c), float(r)) for c, r in pixelCoords]
        return np.array(self.imageItem.imageToLocal(pointsList))

    # --- Region display ---

    def showRegion(self, roi):
        """Display only the given ROI's region of the full image."""
        self._imageItem.setROI(roi)

    def clearRegion(self):
        """Show the full image instead of a region."""
        self._imageItem.clearROI()

    @property
    def isShowingRegion(self) -> bool:
        """Whether the viewport is showing a subregion rather than the full image."""
        return self._imageItem.isShowingRegion

    # --- Items / tools ---

    def addItem(self, item, ignoreBounds: bool = True):
        """Add a graphics item to the viewport.

        By default the item does not contribute to the viewbox's auto-range bounds,
        so the viewport stays centered on the image even when ROIs or other overlays
        extend outside the image extent.
        """
        self._vb.addItem(item, ignoreBounds=ignoreBounds)

    def removeItem(self, item):
        """Remove a graphics item from the viewport."""
        self._vb.removeItem(item)

    def installTool(self, tool: ViewportTool):
        """Shortcut to install a tool's event filter on the imageItem."""
        self._imageItem.installEventFilter(tool)

    def removeTool(self, tool: ViewportTool):
        """Shortcut to remove a tool's event filter from the imageItem."""
        self._imageItem.removeEventFilter(tool)

    def addToolBar(self, toolbar):
        """Add a toolbar to the viewport."""
        self.layout().addWidget(toolbar)

    # --- Escape hatches ---

    @property
    def imageItem(self) -> VardaImageItem:
        """Get the ImageRegionItem for this viewport."""
        return self._imageItem

    @property
    def imageEntity(self) -> VardaRaster:
        return self._imageRenderer.image

    @property
    def viewBox(self) -> pg.ViewBox:
        """Get the ViewBox for this viewport."""
        return self._vb
