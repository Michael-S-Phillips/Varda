import logging

import numpy as np
from PyQt6.QtCore import QObject, QEvent, Qt, QPointF
from PyQt6.QtWidgets import QGraphicsRectItem

from varda.image_rendering.raster_view.viewport import ImageViewport
from varda.rois.varda_roi import VardaROIItem

logger = logging.getLogger(__name__)


class RegionController(QObject):
    dragSpeed: float = 0.5  # Speed multiplier for drag events

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

        # setup roi
        self.sourceViewport.addItem(self.displayROI)
        self.displayROI.sigRegionChanged.connect(self.onRegionChanged)
        self.sourceViewport.sigImageChanged.connect(self.onRegionChanged)
        self.targetViewport.sigImageChanged.connect(self._updateRoiBounds)
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
        """Handle changes to the ROI region."""
        # Update the absolute ROI based on the display ROI changes
        self._calculateAbsoluteROI()
        # Set the absolute ROI on the target viewport
        self.targetViewport.imageItem.setROI(self.internalROI)

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
