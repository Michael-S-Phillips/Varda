import logging

import numpy as np
from PyQt6.QtCore import QObject, QEvent, Qt, QPointF
from PyQt6.QtWidgets import QGraphicsRectItem

from varda.image_rendering.raster_view.image_viewport import ImageViewport
from varda.rois.varda_roi import VardaROIItem

logger = logging.getLogger(__name__)


class RegionController(QObject):
    dragSpeed: float = 0.5  # Speed multiplier for drag events
    zoomFactor: float = 1.2  # ROI scale change per wheel notch (120 units)
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

        # setup roi
        self.sourceViewport.addItem(self.displayROI)
        self.displayROI.sigRegionChanged.connect(self.onRegionChanged)
        # When the source viewport shows a different region (e.g. it is itself the
        # target of a parent controller that zoomed/panned), keep the ROI anchored
        # to the same absolute image coordinates and refresh its bounds.
        self.sourceViewport.sigImageChanged.connect(self._onSourceRegionChanged)
        # Initialize drag state variables
        self._dragStartScenePos = None
        self._isNavigating = False
        self._initialRoiPos = None

        self.enableNavigation()
        self.onRegionChanged()

    def enableNavigation(self):
        """Enable navigation mode for the viewport"""
        self.targetViewport.viewBox.installEventFilter(self)

    def disableNavigation(self):
        """Disable navigation mode for the viewport"""
        self.targetViewport.viewBox.removeEventFilter(self)
        self._resetDragState()

    def eventFilter(self, obj, ev):
        """
        Treat a Graphics-scene mouse-press / move / release triplet
        as a "drag" and update the ROI accordingly.
        """
        # We only care about events that hit *our* ViewBox
        if obj is not self.targetViewport.viewBox:
            return False

        etype = ev.type()

        # zoom (mouse wheel / trackpad two-finger scroll)
        if etype == QEvent.Type.GraphicsSceneWheel:
            self._handleZoom(ev)
            return True  # Accept the event so the ViewBox doesn't also handle it

        # drag START
        if (
            etype == QEvent.Type.GraphicsSceneMousePress
            and ev.button() == Qt.MouseButton.LeftButton
            and ev.modifiers() == Qt.KeyboardModifier.NoModifier
        ):
            # Get click position in scene coordinates
            targetScenePos = self.targetViewport.viewBox.mapToView(ev.pos())

            # abort if we clicked on any items other than the ViewBox/ImageItem/BackgroundRect
            items = self.targetViewport.viewBox.scene().items(ev.scenePos())
            if items:
                for item in items:
                    if (
                        isinstance(item, QGraphicsRectItem)
                        or item is self.targetViewport.imageItem
                        or item is self.targetViewport.viewBox
                    ):
                        continue
                    else:
                        return False

            # No items are in the way, so we can start dragging
            self._isNavigating = True
            self._dragStartScenePos = targetScenePos
            self._initialRoiPos = self.displayROI.pos()

            return True  # Accept the event for navigation

        # drag MOVE
        if etype == QEvent.Type.GraphicsSceneMouseMove and self._isNavigating:
            if ev.buttons() & Qt.MouseButton.LeftButton:
                self._handleNavigationDrag(ev)
                return True  # Accept the event

        # drag END
        if (
            etype == QEvent.Type.GraphicsSceneMouseRelease
            and self._isNavigating
            and ev.button() == Qt.MouseButton.LeftButton
        ):
            self._handleNavigationEnd(ev)
            self._resetDragState()
            return True  # Accept the event

        return False

    def _resetDragState(self):
        """Reset drag state variables"""
        self._isNavigating = False
        self._dragStartScenePos = None
        self._initialRoiPos = self.displayROI.pos()

    def _handleNavigationEnd(self, ev):
        """Handle end of navigation drag"""
        # Reset the drag state
        self._resetDragState()

        # Emit a signal or perform any additional actions needed on drag end
        self.onRegionChanged()
        # This will update the viewport with the new ROI position

    def _handleNavigationDrag(self, ev):
        """Handle ongoing navigation drag"""
        if (
            not self._isNavigating
            or not self._dragStartScenePos
            or not self._initialRoiPos
        ):
            return

        # Get current mouse position in target viewport coordinates
        currentScenePos = self.targetViewport.viewBox.mapToView(ev.pos())

        # Calculate drag distance in target viewport coordinates
        dragDistance = (currentScenePos - self._dragStartScenePos) * self.dragSpeed

        # Map the drag distance to source viewport coordinates
        # We need to account for the scale difference between viewports
        source_drag_distance = self._convertDragToSourceCoordinates(dragDistance)

        # Apply drag to ROI position (invert the drag for intuitive navigation)
        newRoiPos = self._initialRoiPos - source_drag_distance

        # Constrain to bounds
        bounds = self.displayROI.maxBounds
        roi_size = self.displayROI.size()

        newRoiPos.setX(
            max(bounds.left(), min(newRoiPos.x(), bounds.right() - roi_size.x()))
        )
        newRoiPos.setY(
            max(bounds.top(), min(newRoiPos.y(), bounds.bottom() - roi_size.y()))
        )

        # Update ROI position
        self.displayROI.setPos(newRoiPos)
        self.onRegionChanged()

    def _handleZoom(self, ev):
        """Zoom by resizing the ROI, anchored at the cursor.

        Scrolling up shrinks the ROI (the target viewport shows a smaller region,
        i.e. zooms in); scrolling down grows it. Works for both the mouse wheel and
        trackpad two-finger scroll, which arrive as GraphicsSceneWheel events.
        """
        delta = ev.delta()
        if delta == 0:
            return

        # delta > 0 (scroll up) -> scale < 1 -> smaller ROI -> zoom in.
        scale = self.zoomFactor ** (-delta / 120.0)

        roiPos = self.displayROI.pos()
        roiSize = self.displayROI.size()
        bounds = self.displayROI.maxBounds

        # Where the cursor sits within the current ROI (normalised 0..1), so we can
        # keep that point fixed while zooming. The target view is ranged to the ROI
        # region, so a fraction of the view maps to the same fraction of the ROI.
        targetViewRect = self.targetViewport.viewBox.viewRect()
        cursorView = self.targetViewport.viewBox.mapToView(ev.pos())
        fracX = (cursorView.x() - targetViewRect.left()) / targetViewRect.width()
        fracY = (cursorView.y() - targetViewRect.top()) / targetViewRect.height()
        fracX = max(0.0, min(1.0, fracX))
        fracY = max(0.0, min(1.0, fracY))

        # Scale both axes equally to preserve aspect ratio, clamped so the ROI
        # neither grows past its bounds nor shrinks below the minimum size.
        maxScale = min(bounds.width() / roiSize.x(), bounds.height() / roiSize.y())
        minScale = max(self.minRoiSize / roiSize.x(), self.minRoiSize / roiSize.y())
        scale = max(minScale, min(scale, maxScale))

        newWidth = roiSize.x() * scale
        newHeight = roiSize.y() * scale

        # Keep the cursor's anchor point fixed in source coordinates.
        anchorX = roiPos.x() + fracX * roiSize.x()
        anchorY = roiPos.y() + fracY * roiSize.y()
        newX = anchorX - fracX * newWidth
        newY = anchorY - fracY * newHeight

        # Constrain to bounds.
        newX = max(bounds.left(), min(newX, bounds.right() - newWidth))
        newY = max(bounds.top(), min(newY, bounds.bottom() - newHeight))

        self.displayROI.setSize([newWidth, newHeight], update=False)
        self.displayROI.setPos([newX, newY])
        self.onRegionChanged()

    def _convertDragToSourceCoordinates(self, targetDrag: QPointF) -> QPointF:
        """Convert drag distance from target viewport to source viewport coordinates"""
        target_view_rect = self.targetViewport.viewBox.viewRect()
        source_view_rect = self.sourceViewport.viewBox.viewRect()

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

    def onRegionChanged(self):
        """Handle changes to the ROI region driven by the displayROI (local coords)."""
        # Skip while we're repositioning the ROI from absolute coords ourselves;
        # the absolute region is unchanged in that case, so there's nothing to push.
        if self._updatingFromSource:
            return
        # Update the absolute ROI based on the display ROI changes
        self._calculateAbsoluteROI()
        # Set the absolute ROI on the target viewport
        self.targetViewport.imageItem.setROI(self.internalROI)

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
        """Move/resize the displayROI so it still covers self.internalROI.

        Converts the persisted absolute image coordinates back into the source
        viewport's (possibly changed) local coordinates.
        """
        if self.internalROI is None:
            return

        absPoints = [(float(x), float(y)) for x, y in self.internalROI.points]
        localPoints = np.asarray(
            self.sourceViewport.imageItem.imageToLocal(absPoints), dtype=float
        )
        if localPoints.size == 0:
            return

        xMin, yMin = localPoints[:, 0].min(), localPoints[:, 1].min()
        xMax, yMax = localPoints[:, 0].max(), localPoints[:, 1].max()

        # Apply without triggering the forward (local -> absolute) recompute, so
        # the anchored absolute region stays the source of truth.
        self._updatingFromSource = True
        try:
            self.displayROI.setSize([xMax - xMin, yMax - yMin], update=False)
            self.displayROI.setPos(QPointF(xMin, yMin))
        finally:
            self._updatingFromSource = False

    def _updateRoiBounds(self):
        """Update the ROI bounds based on the source viewport image item"""
        self.displayROI.maxBounds = self.sourceViewport.imageItem.boundingRect()

    def _calculateAbsoluteROI(self):
        """
        update self.roi with the absolute coordinate conversion of self.displayROI.
        """
        absolutePoints = []

        for x, y in self.displayROI.roiEntity.points:
            # scenePoint = self.displayROI.mapToScene(QPointF(point[0], point[1]))
            # localImagePoint = self.sourceViewport.imageItem.mapFromScene(scenePoint)
            absoluteImagePoint = self.sourceViewport.imageItem.localToImage(
                QPointF(x, y)
            )
            absolutePoints.append([absoluteImagePoint.x(), absoluteImagePoint.y()])

        # Create new ROI entity with absolute coordinates
        absROI = self.displayROI.roiEntity.clone()
        absROI.points = np.array(absolutePoints)
        self.internalROI = absROI
