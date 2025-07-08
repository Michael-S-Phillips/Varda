import logging
from typing import Dict, List, Optional, Any
from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QRect, QRectF

from varda.app.services.roi_utils.varda_roi import VardaROIItem
from varda.core.entities import ROI

logger = logging.getLogger(__name__)


class ROIDisplayController(QObject):
    """
    Controller for managing the display of ROIs across multiple viewports.

    This controller works directly with ROI entities and displays them
    across registered viewports using VardaROIItem graphics items.
    """

    # Signals
    roiHighlighted = pyqtSignal(str)  # ROI ID highlighted
    roiSelected = pyqtSignal(str)  # ROI ID selected
    displayUpdated = pyqtSignal()  # Display state changed

    def __init__(self, parent=None):
        super().__init__(parent)

        # Dictionary of registered viewports {viewport_id: viewport_object}
        self._viewports: Dict[str, Any] = {}

        # Currently highlighted ROI
        self._highlightedRoi: Optional[str] = None

        # ROI items for each viewport {viewport_id: {roi_id: VardaROIItem}}
        self._roiItems: Dict[str, Dict[str, VardaROIItem]] = {}

        # Blinking state
        self._blinkingEnabled = False
        self._blinkState = False
        self._blinkTimer: Optional[QTimer] = None

        logger.debug("ROIDisplayController initialized")

    def registerViewport(self, viewportId: str, viewport) -> None:
        """Register a viewport for ROI display"""
        self._viewports[viewportId] = viewport
        self._roiItems[viewportId] = {}

        viewport.sigImageChanged.connect(
            lambda vid=viewportId: self._repositionAllRoiItems(vid)
        )
        logger.debug(f"Registered viewport: {viewportId}")

    def unregisterViewport(self, viewportId: str) -> None:
        """Unregister a viewport"""
        if viewportId not in self._viewports:
            return

        # Remove all ROI items from this viewport
        for roiItem in self._roiItems[viewportId].values():
            self._removeRoiItemFromViewport(viewportId, roiItem)
        del self._roiItems[viewportId]

        # Disconnect signals
        self._viewports[viewportId].sigImageChanged.disconnect()
        del self._viewports[viewportId]
        logger.debug(f"Unregistered viewport: {viewportId}")

    def displayRoisForImage(self, rois: List[ROI]) -> None:
        """Display the given list of ROIs on all registered viewports"""
        self._clearAllRois()

        for roi in rois:
            for vid in self._viewports:
                self._addRoiToViewport(vid, roi)

        self.displayUpdated.emit()
        logger.debug(f"Displaying {len(rois)} ROIs")

    def updateRoi(self, roi: ROI) -> None:
        """Update an existing ROI across all viewports"""
        for viewportId, items in self._roiItems.items():
            if roi.id in items:
                item = items[roi.id]
                item.setROIData(roi)
                self._updateRoiItemAppearance(viewportId, item, roi)

        self.displayUpdated.emit()
        logger.debug(f"Updated ROI: {roi.id}")

    def removeRoi(self, roiId: str) -> None:
        """Remove an ROI from every viewport."""
        for vid, items in self._roiItems.items():
            if roiId in items:
                item = items[roiId]
                self._removeRoiItemFromViewport(vid, item)
                del items[roiId]

        if self._highlightedRoi == roiId:
            self._highlightedRoi = None

        self.displayUpdated.emit()
        logger.debug(f"Removed ROI from display: {roiId}")

    def highlightRoi(self, roiId: Optional[str]) -> None:
        """Visually highlight one ROI (deselect others)."""
        if self._highlightedRoi == roiId:
            return
        self._highlightedRoi = roiId
        for items in self._roiItems.values():
            for rid, item in items.items():
                item.setHighlighted(rid == roiId)
        if roiId:
            self.roiHighlighted.emit(roiId)
        logger.debug(f"Highlighted ROI: {roiId}")

    def getHighlightedRoi(self) -> Optional[str]:
        """Get the currently highlighted ROI"""
        return self._highlightedRoi

    # blinking functionality
    def startBlinking(self, intervalMs: int = 500) -> None:
        """Start blinking animation for all ROIs"""
        if self._blinkTimer is None:
            self._blinkTimer = QTimer(self)
            self._blinkTimer.timeout.connect(self._toggleBlinkState)
        self._blinkingEnabled = True
        self._blinkTimer.start(intervalMs)
        logger.debug("Started ROI blinking")

    def stopBlinking(self) -> None:
        """Stop blinking animation"""
        if self._blinkTimer is not None:
            self._blinkTimer.stop()

        self._blinkingEnabled = False
        self._blinkState = False
        self._updateAllRoisVisibility()
        logger.debug("Stopped ROI blinking")

    def isBlinking(self) -> bool:
        """Check if blinking is currently active"""
        return self._blinkingEnabled

    def _clearAllRois(self) -> None:
        """Clear all ROIs from all viewports"""
        for viewportId in list(self._roiItems):
            for roiItem in list(self._roiItems[viewportId].values()):
                self._removeRoiItemFromViewport(viewportId, roiItem)
            self._roiItems[viewportId].clear()

    def _addRoiToAllViewports(self, roi: ROI) -> None:
        """Add an ROI to all registered viewports"""
        for viewportId in self._viewports:
            self._addRoiToViewport(viewportId, roi)

    def _addRoiToViewport(self, viewportId: str, roi: ROI) -> None:
        """Add an ROI to a specific viewport"""
        # Create VardaROIItem from the ROI entity
        roiItem = VardaROIItem.getROI(roi, movable=False)

        # Add to viewport
        self._addRoiItemToViewport(viewportId, roiItem)

        # Set initial appearance
        self._updateRoiItemAppearance(viewportId, roiItem, roi)

        # Store reference
        self._roiItems[viewportId][roi.id] = roiItem

    def _updateRoiItemAppearance(
        self, viewportId, roiItem: VardaROIItem, roi: ROI
    ) -> None:
        """Update a VardaROIItem's appearance based on ROI entity properties"""

        viewport = self._viewports[viewportId]

        # get each bounding rect
        roiSceneRect: QRectF = roiItem.sceneBoundingRect()
        imgSceneRect: QRectF = viewport.imageItem.sceneBoundingRect()

        # 3) only show if they intersect
        visible = imgSceneRect.contains(roiSceneRect) and roi.visible

        if self._blinkingEnabled and not self._blinkState:
            visible = False
        roiItem.setVisible(visible)

        # Handle blinking
        if self._blinkingEnabled and not self._blinkState:
            visible = False

        # Set visibility
        roiItem.setVisible(visible)
        roiItem.refresh()

    def _addRoiItemToViewport(self, viewportId: str, roiItem: VardaROIItem) -> None:
        """Add a ROI item to a viewport"""
        viewport = self._viewports[viewportId]
        viewport.addItem(roiItem)
        roiItem.setCoordinateTransform(
            self._viewports[viewportId].imageItem.coordinateTransform
        )

    def _removeRoiItemFromViewport(
        self, viewportId: str, roiItem: VardaROIItem
    ) -> None:
        """Remove a ROI item from a viewport"""
        viewport = self._viewports[viewportId]
        viewport.removeItem(roiItem)

    def _repositionAllRoiItems(self, viewportId: str) -> None:
        """Called whenever the underlying image region changes."""
        viewport = self._viewports[viewportId]
        for item in self._roiItems[viewportId].values():
            item.setCoordinateTransform(viewport.imageItem.coordinateTransform)
            self._updateRoiItemAppearance(viewportId, item, item.roiEntity)

    def _updateAllRoisVisibility(self) -> None:
        """Update visibility for all ROI items"""
        for viewportId in self._roiItems:
            for roiItem in self._roiItems[viewportId].values():
                roi = roiItem.roiEntity
                self._updateRoiItemAppearance(viewportId, roiItem, roi)

    def _toggleBlinkState(self) -> None:
        """Toggle the blink state and update display"""
        self._blinkState = not self._blinkState
        self._updateAllRoisVisibility()

    def cleanup(self) -> None:
        """Clean up resources"""
        if self._blinkTimer is not None:
            self._blinkTimer.stop()
            self._blinkTimer = None

        self._clearAllRois()

        self._viewports.clear()
        self._roiItems.clear()
        self._highlightedRoi = None

        logger.debug("ROIDisplayController cleaned up")
