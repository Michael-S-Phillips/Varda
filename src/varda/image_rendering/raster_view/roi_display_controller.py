"""ROI display controller — manages VardaROIGraphicsItems across viewports."""

import logging
from typing import Any, Dict, Optional

from PyQt6.QtCore import QObject, pyqtSignal

from varda.rois.roi_collection import ROICollection
from varda.rois.varda_roi_item import VardaROIGraphicsItem

logger = logging.getLogger(__name__)


class ROIDisplayController(QObject):
    """Display ROIs from an ROICollection on registered viewports.

    Listens to collection signals and keeps the visual items in sync.
    """

    roiHighlighted = pyqtSignal(int)  # fid
    roiSelected = pyqtSignal(int)  # fid
    displayUpdated = pyqtSignal()

    def __init__(self, collection: ROICollection, image: Any, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._collection = collection
        self._image = image

        # {viewport_id: viewport_object}
        self._viewports: Dict[str, Any] = {}
        # {viewport_id: {fid: VardaROIGraphicsItem}}
        self._items: Dict[str, Dict[int, VardaROIGraphicsItem]] = {}

        self._highlightedFid: Optional[int] = None

        # Connect collection signals
        self._collection.sigROIAdded.connect(self._onROIAdded)
        self._collection.sigROIRemoved.connect(self._onROIRemoved)
        self._collection.sigROIUpdated.connect(self._onROIUpdated)

    # --- Viewport management ---

    def registerViewport(self, viewportId: str, viewport: Any) -> None:
        self._viewports[viewportId] = viewport
        self._items[viewportId] = {}
        # Display any existing ROIs
        self._displayAllForViewport(viewportId)

    def unregisterViewport(self, viewportId: str) -> None:
        if viewportId not in self._viewports:
            return
        for item in self._items[viewportId].values():
            self._viewports[viewportId].removeItem(item)
        del self._items[viewportId]
        del self._viewports[viewportId]

    # --- Highlight ---

    def highlightROI(self, fid: Optional[int]) -> None:
        if self._highlightedFid == fid:
            return
        self._highlightedFid = fid
        for viewport_items in self._items.values():
            for item_fid, item in viewport_items.items():
                item.setHighlighted(item_fid == fid)
        if fid is not None:
            self.roiHighlighted.emit(fid)

    # --- Signal handlers ---

    def _onROIAdded(self, fid: int) -> None:
        roi = self._collection.getROI(fid)
        pixelCoords = self._collection.getPixelCoordinates(fid, self._image)
        for vid, viewport in self._viewports.items():
            item = VardaROIGraphicsItem(roi, pixelCoords)
            viewport.addItem(item)
            self._items[vid][fid] = item
        self.displayUpdated.emit()

    def _onROIRemoved(self, fid: int) -> None:
        for vid, viewport in self._viewports.items():
            if fid in self._items[vid]:
                viewport.removeItem(self._items[vid][fid])
                del self._items[vid][fid]
        if self._highlightedFid == fid:
            self._highlightedFid = None
        self.displayUpdated.emit()

    def _onROIUpdated(self, fid: int) -> None:
        roi = self._collection.getROI(fid)
        pixelCoords = self._collection.getPixelCoordinates(fid, self._image)
        for vid in self._viewports:
            if fid in self._items[vid]:
                self._items[vid][fid].updateData(roi, pixelCoords)
        self.displayUpdated.emit()

    # --- Internal ---

    def _displayAllForViewport(self, viewportId: str) -> None:
        viewport = self._viewports[viewportId]
        for fid in self._collection.fids:
            roi = self._collection.getROI(fid)
            pixelCoords = self._collection.getPixelCoordinates(fid, self._image)
            item = VardaROIGraphicsItem(roi, pixelCoords)
            viewport.addItem(item)
            self._items[viewportId][fid] = item

    def cleanup(self) -> None:
        for vid, viewport in self._viewports.items():
            for item in self._items[vid].values():
                viewport.removeItem(item)
            self._items[vid].clear()
        self._viewports.clear()
        self._items.clear()
        self._highlightedFid = None
