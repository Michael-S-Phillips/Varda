import logging
from typing import Dict, List, Optional, Any
from PyQt6.QtCore import QObject, pyqtSignal, QTimer
from PyQt6.QtGui import QColor

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
        logger.debug(f"Registered viewport: {viewportId}")

    def unregisterViewport(self, viewportId: str) -> None:
        """Unregister a viewport"""
        if viewportId in self._viewports:
            # Remove all ROI items from this viewport
            if viewportId in self._roiItems:
                for roiItem in self._roiItems[viewportId].values():
                    self._removeRoiItemFromViewport(viewportId, roiItem)
                del self._roiItems[viewportId]

            del self._viewports[viewportId]
            logger.debug(f"Unregistered viewport: {viewportId}")

    def displayRoisForImage(self, rois: List[ROI]) -> None:
        """Display the given list of ROIs on all registered viewports"""
        # Clear all existing ROI items
        self.clearAllRois()

        # Add the new ROIs
        for roi in rois:
            self._addRoiToAllViewports(roi)

        self.displayUpdated.emit()
        logger.debug(f"Displaying {len(rois)} ROIs")

    def updateRoi(self, roi: ROI) -> None:
        """Update an existing ROI across all viewports"""
        roiId = roi.id

        # Update the ROI items in all viewports
        for viewportId in self._roiItems:
            if roiId in self._roiItems[viewportId]:
                roiItem = self._roiItems[viewportId][roiId]
                roiItem.setROIData(roi)
                self._updateRoiItemAppearance(roiItem, roi)

        self.displayUpdated.emit()
        logger.debug(f"Updated ROI: {roiId}")

    def removeRoi(self, roiId: str) -> None:
        """Remove an ROI from all viewports"""
        # Remove ROI items from all viewports
        for viewportId in self._roiItems:
            if roiId in self._roiItems[viewportId]:
                roiItem = self._roiItems[viewportId][roiId]
                self._removeRoiItemFromViewport(viewportId, roiItem)
                del self._roiItems[viewportId][roiId]

        if self._highlightedRoi == roiId:
            self._highlightedRoi = None

        self.displayUpdated.emit()
        logger.debug(f"Removed ROI from display: {roiId}")

    def highlightRoi(self, roiId: Optional[str]) -> None:
        """Highlight a specific ROI (or clear highlight if None)"""
        if self._highlightedRoi != roiId:
            self._highlightedRoi = roiId
            self._updateAllRoiHighlighting()

            if roiId:
                self.roiHighlighted.emit(roiId)
                logger.debug(f"Highlighted ROI: {roiId}")

    def getHighlightedRoi(self) -> Optional[str]:
        """Get the currently highlighted ROI"""
        return self._highlightedRoi

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

    def clearAllRois(self) -> None:
        """Clear all ROIs from all viewports"""
        for viewportId in list(self._roiItems.keys()):
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

        # Set initial appearance
        self._updateRoiItemAppearance(roiItem, roi)

        # Add to viewport
        self._addRoiItemToViewport(viewportId, roiItem)

        # Store reference
        self._roiItems[viewportId][roi.id] = roiItem

    def _updateRoiItemAppearance(self, roiItem: VardaROIItem, roi: ROI) -> None:
        """Update a VardaROIItem's appearance based on ROI entity properties"""
        # Get display properties from the ROI entity
        isHighlighted = roi.id == self._highlightedRoi
        isVisible = roi.visible

        # Handle blinking
        if self._blinkingEnabled and not self._blinkState:
            isVisible = False

        # Set visibility
        roiItem.setVisible(isVisible)

        # Update appearance - the VardaROIItem will handle pen/brush from the ROI entity
        roiItem.refresh()

    def _updateAllRoiHighlighting(self) -> None:
        """Update highlighting for all ROI items"""
        for viewportId in self._roiItems:
            for roiId, roiItem in self._roiItems[viewportId].items():
                # The highlighting will be handled by the VardaROIItem based on selection state
                roiItem.refresh()

    def _updateAllRoisVisibility(self) -> None:
        """Update visibility for all ROI items"""
        for viewportId in self._roiItems:
            for roiItem in self._roiItems[viewportId].values():
                roi = roiItem.roiEntity
                self._updateRoiItemAppearance(roiItem, roi)

    def _toggleBlinkState(self) -> None:
        """Toggle the blink state and update display"""
        self._blinkState = not self._blinkState
        self._updateAllRoisVisibility()

    def _addRoiItemToViewport(self, viewportId: str, roiItem: VardaROIItem) -> None:
        """Add a ROI item to a viewport"""
        viewport = self._viewports[viewportId]
        viewport.addItem(roiItem)

    def _removeRoiItemFromViewport(
        self, viewportId: str, roiItem: VardaROIItem
    ) -> None:
        """Remove a ROI item from a viewport"""
        viewport = self._viewports[viewportId]
        viewport.removeItem(roiItem)

    def cleanup(self) -> None:
        """Clean up resources"""
        if self._blinkTimer is not None:
            self._blinkTimer.stop()
            self._blinkTimer = None

        self.clearAllRois()

        self._viewports.clear()
        self._roiItems.clear()
        self._highlightedRoi = None

        logger.debug("ROIDisplayController cleaned up")
