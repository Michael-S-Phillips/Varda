import logging

import numpy as np
from PyQt6.QtCore import QObject, QPointF

from varda.image_rendering.raster_view.image_viewport import ImageViewport
from varda.rois.varda_roi import VardaROIItem

logger = logging.getLogger(__name__)


class RegionController(QObject):
    """Drives what a target viewport shows from an ROI placed on a source viewport.

    A `displayROI` lives on the source viewport; its region (in absolute image
    coordinates, tracked as `internalROI`) is pushed to the target viewport via
    `showRegion`. Navigating the target viewport (the target has self-navigation
    disabled) pans/zooms the ROI instead of the target's own view:

      - panning the target moves the ROI on the source,
      - zooming the target resizes the ROI on the source.
    """

    dragSpeed: float = 0.5  # Speed multiplier for drag events
    minRoiSize: float = 4.0  # Smallest allowed ROI dimension, in source pixels

    def __init__(
        self,
        sourceViewport: ImageViewport,
        targetViewport: ImageViewport,
        roi: VardaROIItem,
        parentRegionController: "RegionController" = None,
        parent=None,
    ):
        super().__init__(parent)
        self.sourceViewport = sourceViewport
        self.targetViewport = targetViewport
        self.parentRegionController = parentRegionController
        # we'll be updating it directly, using the data from the source viewport
        self.internalROI = None
        self.displayROI = roi
        self._updateRoiBounds()

        # Guard against re-entrant updates while we reposition the ROI ourselves.
        self._updatingFromSource = False
        # ROI position captured at the start of a pan gesture.
        self._initialRoiPos = None

        # setup roi
        self.sourceViewport.addItem(self.displayROI)
        self.displayROI.sigRegionChanged.connect(self.onRegionChanged)
        # When the source viewport shows a different region (e.g. it is itself the
        # target of a parent controller that zoomed/panned), keep the ROI anchored
        # to the same absolute image coordinates and refresh its bounds.
        self.sourceViewport.sigImageChanged.connect(self._onSourceRegionChanged)

        # Navigation of the target viewport drives the ROI rather than the target's view.
        self.targetViewport.sigPanStarted.connect(self._onPanStarted)
        self.targetViewport.sigPanned.connect(self._onPanned)
        self.targetViewport.sigZoomed.connect(self._onZoomed)

        self.onRegionChanged()

    # --- Navigation gesture handlers ---

    def _onPanStarted(self, startView: QPointF):
        """Capture the ROI position so the pan can be applied relative to it."""
        self._initialRoiPos = self.displayROI.pos()

    def _onPanned(self, currentView: QPointF, startView: QPointF):
        """Move the ROI to follow a drag in the target viewport."""
        if self._initialRoiPos is None:
            return

        # Drag distance in target view coordinates, mapped to source coordinates.
        dragDistance = (currentView - startView) * self.dragSpeed
        sourceDrag = self._convertDragToSourceCoordinates(dragDistance)

        # Invert the drag for intuitive "grab the view" navigation.
        newRoiPos = self._initialRoiPos - sourceDrag
        self._clampPosToBounds(newRoiPos, self.displayROI.size())
        self.displayROI.setPos(newRoiPos)
        self.onRegionChanged()

    def _onZoomed(self, scaleFactor: float, anchorFraction: QPointF):
        """Resize the ROI about the cursor anchor to zoom the target viewport.

        `scaleFactor` < 1 shrinks the ROI (target shows a smaller region, i.e. zooms
        in); `anchorFraction` is the cursor's normalised position within the ROI, kept
        fixed so the zoom stays centred on the cursor.
        """
        roiPos = self.displayROI.pos()
        roiSize = self.displayROI.size()
        bounds = self.displayROI.maxBounds
        fracX, fracY = anchorFraction.x(), anchorFraction.y()

        # Scale both axes equally to preserve aspect ratio, clamped so the ROI neither
        # grows past its bounds nor shrinks below the minimum size.
        maxScale = min(bounds.width() / roiSize.x(), bounds.height() / roiSize.y())
        minScale = max(self.minRoiSize / roiSize.x(), self.minRoiSize / roiSize.y())
        scale = max(minScale, min(scaleFactor, maxScale))

        newWidth = roiSize.x() * scale
        newHeight = roiSize.y() * scale

        # Keep the cursor's anchor point fixed in source coordinates.
        anchorX = roiPos.x() + fracX * roiSize.x()
        anchorY = roiPos.y() + fracY * roiSize.y()
        newPos = QPointF(anchorX - fracX * newWidth, anchorY - fracY * newHeight)
        self._clampPosToBounds(newPos, QPointF(newWidth, newHeight))

        self.displayROI.setSize([newWidth, newHeight], update=False)
        self.displayROI.setPos(newPos)
        self.onRegionChanged()

    def _clampPosToBounds(self, pos: QPointF, size: QPointF):
        """Clamp an ROI position (in place) so the ROI stays within maxBounds."""
        bounds = self.displayROI.maxBounds
        pos.setX(max(bounds.left(), min(pos.x(), bounds.right() - size.x())))
        pos.setY(max(bounds.top(), min(pos.y(), bounds.bottom() - size.y())))

    def _convertDragToSourceCoordinates(self, targetDrag: QPointF) -> QPointF:
        """Convert drag distance from target viewport to source viewport coordinates"""
        target_view_rect = self.targetViewport.viewRect()
        source_view_rect = self.sourceViewport.viewRect()

        # Calculate separate scale factors for X and Y
        if (
            target_view_rect.width() > 0
            and target_view_rect.height() > 0
            and source_view_rect.width() > 0
            and source_view_rect.height() > 0
        ):
            scale_x = source_view_rect.width() / target_view_rect.width()
            scale_y = source_view_rect.height() / target_view_rect.height()

            return QPointF(targetDrag.x() * scale_x, targetDrag.y() * scale_y)

        return targetDrag

    # --- Region sync ---

    def onRegionChanged(self):
        """Handle changes to the ROI region driven by the displayROI (local coords)."""
        # Skip while we're repositioning the ROI from absolute coords ourselves;
        # the absolute region is unchanged in that case, so there's nothing to push.
        if self._updatingFromSource:
            return
        # Update the absolute ROI based on the display ROI changes
        self._calculateAbsoluteROI()
        # Set the absolute ROI on the target viewport
        self.targetViewport.showRegion(self.internalROI)

    def _onSourceRegionChanged(self):
        """Handle the source viewport emitting a new image.

        This fires both when the source pans/zooms (its coordinate system changes)
        and when its render data changes (band/stretch). The displayROI is anchored
        to absolute image coordinates, so we re-derive its local position to keep it
        covering the same absolute region, then re-push that region to the target so
        it re-extracts from the source's (possibly new) render data.
        """
        self._updateRoiBounds()
        self._repositionDisplayROIFromAbsolute()
        self.onRegionChanged()

    def _repositionDisplayROIFromAbsolute(self):
        """Move/resize the displayROI so it stays within the displayed region.

        Converts the persisted absolute image coordinates back into the source
        viewport's (possibly changed) local coordinates, then clamps to the
        displayed region. While the ROI fits inside the region the clamp is a
        no-op, so it stays anchored to its image position; once the region edge
        reaches it, the clamp pulls it along so it never goes offscreen. The
        clamped position becomes the new anchor via the onRegionChanged() call in
        _onSourceRegionChanged, so the target viewport follows.

        If the region is smaller than the ROI, the clamp is best-effort: the ROI
        pins to the region's top-left and overflows the far edges (no resize).
        """
        if self.internalROI is None:
            return

        absPoints = [(float(x), float(y)) for x, y in self.internalROI.points]
        localPoints = np.asarray(
            self.sourceViewport.imageToLocal(absPoints), dtype=float
        )
        if localPoints.size == 0:
            return

        xMin, yMin = localPoints[:, 0].min(), localPoints[:, 1].min()
        xMax, yMax = localPoints[:, 0].max(), localPoints[:, 1].max()

        size = QPointF(xMax - xMin, yMax - yMin)
        pos = QPointF(xMin, yMin)
        self._clampPosToBounds(pos, size)

        # Set the (possibly clamped) geometry without triggering the forward
        # (local -> absolute) recompute mid-update; _onSourceRegionChanged calls
        # onRegionChanged() afterward, which re-derives the anchor from this
        # position (a no-op round-trip unless the clamp moved the ROI).
        self._updatingFromSource = True
        try:
            self.displayROI.setSize([size.x(), size.y()], update=False)
            self.displayROI.setPos(pos)
        finally:
            self._updatingFromSource = False

    def _updateRoiBounds(self):
        """Update the ROI bounds based on the source viewport image item"""
        self.displayROI.maxBounds = self.sourceViewport.imageBounds()

    def _calculateAbsoluteROI(self):
        """
        update self.roi with the absolute coordinate conversion of self.displayROI.
        """
        localPoints = [
            (float(x), float(y)) for x, y in self.displayROI.roiEntity.points
        ]

        # Create new ROI entity with absolute coordinates
        absROI = self.displayROI.roiEntity.clone()
        absROI.points = np.asarray(self.sourceViewport.localToImage(localPoints))
        self.internalROI = absROI
