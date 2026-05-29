from typing import Protocol

import pyqtgraph as pg
from PyQt6.QtCore import pyqtSignal, QPointF, QRectF
from varda.common.entities import Image
from varda.image_rendering.raster_view import VardaImageItem


class Viewport(Protocol):
    """
    Protocol for a viewport, which is a widget that displays image data.
    The purpose of this is to generalize an interface that can be used by controllers/viewport_tools/workspaces.

    The intent-level methods below are the preferred surface; `imageItem`/`imageEntity`/
    `viewBox` remain available as escape hatches for cases the facade doesn't yet cover.
    """

    sigImageChanged: pyqtSignal

    # Navigation gestures (see ImageViewport for semantics).
    sigPanStarted: pyqtSignal
    sigPanned: pyqtSignal
    sigPanEnded: pyqtSignal
    sigZoomed: pyqtSignal
    sigViewRangeChangedManually: pyqtSignal

    def enableSelfUpdating(self):
        """Enable self-updating of the image item."""

    def disableSelfUpdating(self):
        """Disable self-updating of the image item."""

    def enableSelfNavigation(self):
        """Let mouse gestures pan/zoom this viewport's own view range."""

    def disableSelfNavigation(self):
        """Stop the viewport from panning/zooming itself; gestures are still emitted."""

    def refresh(self):
        """Refresh the image display with current settings."""

    def addItem(self, item):
        """Add a graphics item to the viewport"""

    def removeItem(self, item):
        """Remove a graphics item from the viewport"""

    def installTool(self, tool):
        """Install a tool on the viewport."""

    def removeTool(self, tool):
        """Remove a tool from the viewport."""

    def addToolBar(self, toolbar):
        """Add a toolbar to the viewport."""

    # --- View / range ---

    def mapToView(self, point: QPointF) -> QPointF:
        """Map a point from ViewBox-local coordinates to view (data) coordinates."""
        ...

    def viewRect(self) -> QRectF:
        """The currently displayed range, in view (data) coordinates."""
        ...

    def setViewRange(self, rect: QRectF, padding: float = 0):
        """Set the displayed range, in view (data) coordinates."""

    # --- Coordinate conversion ---

    def localToImage(self, point):
        """Convert viewport-local coordinates to full-image pixel coordinates."""
        ...

    def imageToLocal(self, point):
        """Convert full-image pixel coordinates to viewport-local coordinates."""
        ...

    def imageBounds(self) -> QRectF:
        """The bounding rectangle of the displayed image, in viewport-local coordinates."""
        ...

    def pixelToLocalCoords(self, pixelCoords):
        """Convert full-image pixel coordinates to viewport-local coordinates (array form)."""
        ...

    # --- Region display ---

    def showRegion(self, roi):
        """Display only the given ROI's region of the full image."""

    def clearRegion(self):
        """Show the full image instead of a region."""

    @property
    def isShowingRegion(self) -> bool:
        """Whether the viewport is showing a subregion rather than the full image."""
        ...

    # --- Escape hatches ---

    @property
    def imageItem(self) -> VardaImageItem:
        """Get the ImageRegionItem for this viewport."""
        ...

    @property
    def imageEntity(self) -> Image:
        """Get the Image entity for this viewport."""
        ...

    @property
    def viewBox(self) -> pg.ViewBox:
        """Get the ViewBox for this viewport."""
        ...
