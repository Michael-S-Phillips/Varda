from PyQt6.QtCore import pyqtSignal, QPointF, QRectF, QEvent, Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QGraphicsRectItem
import pyqtgraph as pg
import numpy as np

from varda import log
from varda.common.entities import VardaRaster
from varda.image_rendering import ImageRenderer
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

    The viewport owns navigation: it intercepts mouse drag/scroll on its ViewBox and
    translates them into high-level gestures (`sigPanned`, `sigZoomed`). Those gestures are
    always emitted so external controllers (e.g. RegionController) can react to them.
    Whether the viewport *also* applies a gesture to its own view range is governed by
    `enableSelfNavigation()`/`disableSelfNavigation()`, mirroring the self-updating pattern.
    """

    sigImageChanged = pyqtSignal()

    # High-level navigation gestures, emitted on user interaction regardless of whether
    # self-navigation is enabled. Positions are in view (data) coordinates.
    sigPanStarted = pyqtSignal(QPointF)  # press position
    sigPanned = pyqtSignal(QPointF, QPointF)  # (current position, start position)
    sigPanEnded = pyqtSignal()
    # (scaleFactor, anchorFraction): scaleFactor < 1 zooms in; anchorFraction is the
    # cursor position normalised to [0, 1] within the current view rect.
    sigZoomed = pyqtSignal(float, QPointF)
    # Emitted whenever a self-applied gesture changes this viewport's view range. Mirrors
    # pyqtgraph's viewBox.sigRangeChangedManually (which no longer fires, since navigation
    # no longer goes through the viewBox's native handling).
    sigViewRangeChangedManually = pyqtSignal()

    zoomFactor: float = 1.2  # View scale change per wheel notch (120 units)

    def __init__(self, imageRenderer: ImageRenderer, parent=None):
        super().__init__(parent)
        self.selfUpdating = True
        self._selfNavigating = True

        self._imageRenderer = imageRenderer
        self._imageItem: VardaImageItem = VardaImageItem(self._imageRenderer)

        self._overlayImageRenderer: ImageRenderer | None = None
        self._overlayImageItem: VardaImageItem | None = None

        self._vb = pg.ViewBox(lockAspect=True, invertY=True)
        # The viewport drives navigation itself (see eventFilter), so the ViewBox's own
        # mouse handling is disabled to avoid competing with it.
        self._vb.setMouseEnabled(x=False, y=False)

        self._vb.addItem(self._imageItem)
        self._vb.keyPressEvent = lambda event: None
        self._gv = pg.GraphicsView()
        self._gv.setCentralItem(self._vb)
        layout = QVBoxLayout(self)
        layout.addWidget(self._gv)
        self.setLayout(layout)

        # Navigation drag state
        self._isNavigating = False
        self._navStartView: QPointF | None = None
        self._vb.installEventFilter(self)

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
        self._selfNavigating = True

    def disableSelfNavigation(self):
        """Stop this viewport from panning/zooming itself in response to gestures.

        Gestures are still detected and emitted as signals; the viewport just doesn't
        move its own view. Used when an external controller (e.g. RegionController)
        drives what the viewport shows.
        """
        self._selfNavigating = False

    def eventFilter(self, obj, ev):
        """Translate mouse drag/scroll on the ViewBox into high-level navigation gestures.

        A drag (left button, no modifier) is treated as a pan and a wheel/trackpad scroll
        as a zoom. Gestures are emitted as signals and, when self-navigation is enabled,
        applied to this viewport's own view range.
        """
        if obj is not self._vb:
            return False

        etype = ev.type()

        if etype == QEvent.Type.GraphicsSceneWheel:
            return self._handleWheel(ev)

        if (
            etype == QEvent.Type.GraphicsSceneMousePress
            and ev.button() == Qt.MouseButton.LeftButton
            and ev.modifiers() == Qt.KeyboardModifier.NoModifier
        ):
            return self._handlePanStart(ev)

        if (
            etype == QEvent.Type.GraphicsSceneMouseMove
            and self._isNavigating
            and ev.buttons() & Qt.MouseButton.LeftButton
        ):
            return self._handlePanMove(ev)

        if (
            etype == QEvent.Type.GraphicsSceneMouseRelease
            and self._isNavigating
            and ev.button() == Qt.MouseButton.LeftButton
        ):
            return self._handlePanEnd(ev)

        return False

    def _handlePanStart(self, ev) -> bool:
        # Don't start a pan if the press landed on an interactive overlay (e.g. an ROI or
        # its handles). Only the background rect, our image item, or the viewBox itself
        # are "empty" surfaces that should begin a pan.
        for item in self._vb.scene().items(ev.scenePos()):
            if not (
                isinstance(item, QGraphicsRectItem)
                or item is self._imageItem
                or item is self._vb
            ):
                return False

        self._isNavigating = True
        self._navStartView = self._vb.mapToView(ev.pos())
        self.sigPanStarted.emit(self._navStartView)
        return True

    def _handlePanMove(self, ev) -> bool:
        currentView = self._vb.mapToView(ev.pos())
        self.sigPanned.emit(currentView, self._navStartView)
        if self._selfNavigating:
            # Shift the view so the grabbed data point stays under the cursor.
            delta = self._navStartView - currentView
            self.setViewRange(self.viewRect().translated(delta.x(), delta.y()))
            self.sigViewRangeChangedManually.emit()
        return True

    def _handlePanEnd(self, ev) -> bool:
        self._isNavigating = False
        self._navStartView = None
        self.sigPanEnded.emit()
        return True

    def _handleWheel(self, ev) -> bool:
        delta = ev.delta()
        if delta == 0:
            return True

        # delta > 0 (scroll up) -> scaleFactor < 1 -> smaller view range -> zoom in.
        scaleFactor = self.zoomFactor ** (-delta / 120.0)

        rect = self.viewRect()
        cursorView = self._vb.mapToView(ev.pos())
        fracX = max(0.0, min(1.0, (cursorView.x() - rect.left()) / rect.width()))
        fracY = max(0.0, min(1.0, (cursorView.y() - rect.top()) / rect.height()))
        anchorFraction = QPointF(fracX, fracY)

        self.sigZoomed.emit(scaleFactor, anchorFraction)
        if self._selfNavigating:
            self._applyZoom(scaleFactor, anchorFraction)
        return True

    def _applyZoom(self, scaleFactor: float, anchorFraction: QPointF):
        """Scale the view range about the anchor point, keeping it fixed under the cursor."""
        rect = self.viewRect()
        newWidth = rect.width() * scaleFactor
        newHeight = rect.height() * scaleFactor
        anchorX = rect.left() + anchorFraction.x() * rect.width()
        anchorY = rect.top() + anchorFraction.y() * rect.height()
        newLeft = anchorX - anchorFraction.x() * newWidth
        newTop = anchorY - anchorFraction.y() * newHeight
        self.setViewRange(QRectF(newLeft, newTop, newWidth, newHeight))
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

    # legacy / lower level access. Most code shouldn't need to use these.

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
