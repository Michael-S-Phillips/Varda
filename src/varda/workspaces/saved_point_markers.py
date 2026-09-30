"""Keep the saved points of a workspace marked on its viewport(s) as circles
in their colour, with the point selected in the Points Manager highlighted."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

import numpy as np
from psygnal import SignalInstance
from PyQt6.QtCore import QObject, QPointF
from PyQt6.QtGui import QColor

from varda.image_rendering.raster_view.viewport_protocol import PointOverlayHandle
from varda.points.point_collection import PointCollection


class MarkerViewport(Protocol):
    # Fires when the viewport's local coordinates move (it shows a region of
    # the image and was panned), so markers must be re-mapped.
    sigImageChanged: SignalInstance

    def pixelToLocalCoords(self, pixelCoords: np.ndarray) -> np.ndarray: ...

    def addPointOverlay(
        self, pos: QPointF, color: QColor, symbol: str = "x"
    ) -> PointOverlayHandle: ...


class SavedPointMarkers(QObject):
    def __init__(
        self,
        collection: PointCollection,
        viewports: Sequence[MarkerViewport],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._collection = collection
        self._viewports = list(viewports)
        self._markers: dict[int, list[PointOverlayHandle]] = {}
        self._highlighted: int | None = None
        collection.sigCollectionChanged.connect(self.refresh)
        for viewport in self._viewports:
            viewport.sigImageChanged.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        for handles in self._markers.values():
            for handle in handles:
                handle.remove()
        self._markers.clear()
        for point in self._collection.getAllPoints():
            centre = np.array([[point.x + 0.5, point.y + 0.5]], dtype=float)
            handles = []
            for viewport in self._viewports:
                (local,) = viewport.pixelToLocalCoords(centre)
                handle = viewport.addPointOverlay(
                    QPointF(float(local[0]), float(local[1])),
                    point.color.toQColor(),
                    symbol="o",
                )
                handle.setHighlighted(point.fid == self._highlighted)
                handles.append(handle)
            self._markers[point.fid] = handles

    def highlight(self, fid: int | None) -> None:
        self._highlighted = fid
        for pointFid, handles in self._markers.items():
            for handle in handles:
                handle.setHighlighted(pointFid == fid)
