"""ROI display controller — manages VardaROIGraphicsItems across viewports."""

from __future__ import annotations

import logging
from typing import Any, Callable

import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal

from varda.rois.roi_collection import ROICollection
from varda.rois.varda_roi_item import VardaROIGraphicsItem
from varda.image_rendering.raster_view.image_viewport import ImageViewport

logger = logging.getLogger(__name__)


class ROIDisplayController(QObject):
    """Display ROIs from an ROICollection on registered viewports.

    Listens to collection signals and keeps the visual items in sync.
    Handles coordinate conversion for viewports that display subregions.
    """

    roiHighlighted = pyqtSignal(int)  # fid
    roiSelected = pyqtSignal(int)  # fid
    displayUpdated = pyqtSignal()

    def __init__(
        self, collection: ROICollection, image: Any, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._collection = collection
        self._image = image

        # {viewport_id: viewport_object}
        self._viewports: dict[str, ImageViewport] = {}
        # {viewport_id: {fid: VardaROIGraphicsItem}}
        self._items: dict[str, dict[int, VardaROIGraphicsItem]] = {}
        # {viewport_id: callback} for signal disconnection
        self._viewportCallbacks: dict[str, Callable] = {}

        self._highlightedFid: int | None = None

        # Connect collection signals
        self._collection.sigROIAdded.connect(self._onROIAdded)
        self._collection.sigROIRemoved.connect(self._onROIRemoved)
        self._collection.sigROIUpdated.connect(self._onROIUpdated)

    # --- Viewport management ---

    def registerViewport(self, viewportId: str, viewport: Any) -> None:
        self._viewports[viewportId] = viewport
        self._items[viewportId] = {}

        # Listen for region changes so ROI positions update when viewport pans
        def callback(vid=viewportId):
            self._refreshViewport(vid)

        self._viewportCallbacks[viewportId] = callback
        viewport.sigImageChanged.connect(callback)
        # Display any existing ROIs
        self._displayAllForViewport(viewportId)

    def unregisterViewport(self, viewportId: str) -> None:
        if viewportId not in self._viewports:
            return
        viewport = self._viewports[viewportId]
        viewport.sigImageChanged.disconnect(self._viewportCallbacks[viewportId])
        del self._viewportCallbacks[viewportId]
        for item in self._items[viewportId].values():
            viewport.removeItem(item)
        del self._items[viewportId]
        del self._viewports[viewportId]

    # --- Highlight ---

    def highlightROI(self, fid: int | None) -> None:
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
            localCoords = viewport.pixelToLocalCoords(pixelCoords)
            item = VardaROIGraphicsItem(roi, localCoords)
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
        for vid, viewport in self._viewports.items():
            if fid in self._items[vid]:
                localCoords = viewport.pixelToLocalCoords(pixelCoords)
                self._items[vid][fid].updateData(roi, localCoords)
        self.displayUpdated.emit()

    # --- Internal ---

    def _refreshViewport(self, viewportId: str) -> None:
        """Recompute local coordinates for all ROI items on a viewport."""
        viewport = self._viewports[viewportId]
        for fid, item in self._items[viewportId].items():
            roi = self._collection.getROI(fid)
            pixelCoords = self._collection.getPixelCoordinates(fid, self._image)
            localCoords = viewport.pixelToLocalCoords(pixelCoords)
            item.updateData(roi, localCoords)

    def _displayAllForViewport(self, viewportId: str) -> None:
        viewport = self._viewports[viewportId]
        for fid in self._collection.fids:
            roi = self._collection.getROI(fid)
            pixelCoords = self._collection.getPixelCoordinates(fid, self._image)
            localCoords = viewport.pixelToLocalCoords(pixelCoords)
            item = VardaROIGraphicsItem(roi, localCoords)
            viewport.addItem(item)
            self._items[viewportId][fid] = item

    def cleanup(self) -> None:
        for vid, viewport in self._viewports.items():
            if vid in self._viewportCallbacks:
                viewport.sigImageChanged.disconnect(self._viewportCallbacks[vid])
            for item in self._items[vid].values():
                viewport.removeItem(item)
            self._items[vid].clear()
        self._viewports.clear()
        self._items.clear()
        self._viewportCallbacks.clear()
        self._highlightedFid = None
