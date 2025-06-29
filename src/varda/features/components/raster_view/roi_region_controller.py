import logging

from PyQt6.QtCore import QObject, QEvent, Qt
import pyqtgraph as pg

from varda.features.components.raster_view.raster_viewport import ImageViewport

logger = logging.getLogger(__name__)


class ROIRegionController(QObject):
    dragSpeed: float = 0.5  # Speed multiplier for drag events

    def __init__(
        self,
        sourceViewport: ImageViewport,
        targetViewport: ImageViewport,
        roi: pg.ROI,
        parent=None,
    ):
        super().__init__(parent)
        self.sourceViewport = sourceViewport

        self.targetViewport = targetViewport
        # we'll be updating it directly, using the data from the source viewport
        self.targetViewport.disableSelfUpdating()
        self.roi = roi

        # setup roi
        self.sourceViewport.vb.addItem(roi)
        self.roi.sigRegionChanged.connect(self.onRegionChanged)
        self.sourceViewport.imageItem.sigImageChanged.connect(self._updateRoiBounds)

        # Initialize drag state variables
        self._dragStartScenePos = None
        self._isNavigating = False
        self._initialRoiPos = None

        self.enableNavigation()

    def enableNavigation(self):
        """Enable navigation mode for the viewport"""
        self.targetViewport.vb.installEventFilter(self)

    def disableNavigation(self):
        """Disable navigation mode for the viewport"""
        self.targetViewport.vb.removeEventFilter(self)
        self._resetDragState()

    def eventFilter(self, obj, ev):
        """
        Treat a Graphics-scene mouse-press / move / release triplet
        as a "drag" and update the ROI accordingly.
        """
        # We only care about events that hit *our* ViewBox
        if obj is not self.targetViewport.vb:
            return False

        etype = ev.type()

        # drag START
        if (
            etype == QEvent.Type.GraphicsSceneMousePress
            and ev.button() == Qt.MouseButton.LeftButton
        ):
            # Get click position in target viewport scene coordinates
            targetScenePos = self.targetViewport.vb.mapToView(ev.pos())

            # Check if there's an ROI on the target viewport that should handle this click
            # Let any ROI on the target viewport handle its own interactions first
            targetItems = self.targetViewport.vb.scene().items(ev.scenePos())
            for item in targetItems:
                if isinstance(item, pg.ROI):
                    # Let the target viewport's ROI handle this
                    return False

            # Start navigation drag
            self._isNavigating = True
            self._dragStartScenePos = targetScenePos
            self._initialRoiPos = self.roi.pos()

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
        self._initialRoiPos = self.roi.pos()

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
        currentScenePos = self.targetViewport.vb.mapToView(ev.pos())

        # Calculate drag distance in target viewport coordinates
        dragDistance = (currentScenePos - self._dragStartScenePos) * self.dragSpeed

        # Map the drag distance to source viewport coordinates
        # We need to account for the scale difference between viewports
        source_drag_distance = dragDistance

        # If the viewports have different scales, adjust the drag distance
        target_view_rect = self.targetViewport.vb.viewRect()
        source_view_rect = self.sourceViewport.vb.viewRect()

        if target_view_rect.width() > 0 and source_view_rect.width() > 0:
            scale_factor = source_view_rect.width() / target_view_rect.width()
            source_drag_distance = dragDistance * scale_factor

        # Apply drag to ROI position (invert the drag for intuitive navigation, and apply speed)
        newRoiPos = self._initialRoiPos - source_drag_distance

        # Constrain to bounds

        bounds = self.roi.maxBounds
        roi_size = self.roi.size()

        newRoiPos.setX(
            max(bounds.left(), min(newRoiPos.x(), bounds.right() - roi_size.x()))
        )
        newRoiPos.setY(
            max(bounds.top(), min(newRoiPos.y(), bounds.bottom() - roi_size.y()))
        )

        # Update ROI position
        self.roi.setPos(newRoiPos, update=False)  # Avoid recursive updates
        self.onRegionChanged()  # Manually trigger update

        logger.debug("ROI position updated to: %s", newRoiPos)

    def onRegionChanged(self):
        """Handle changes to the ROI region."""
        regionData = self.roi.getArrayRegion(
            self.sourceViewport.imageItem.image, self.sourceViewport.imageItem
        )
        self.targetViewport.imageItem.setImage(
            regionData, levels=self.sourceViewport.imageItem.levels
        )

    def _updateRoiBounds(self):
        """Update the ROI bounds based on the source viewport image item"""
        self.roi.maxBounds = self.sourceViewport.imageItem.boundingRect()
