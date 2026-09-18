"""Mark every plotted pixel spectrum on the image(s) it came from.

Each pixel curve on any of a workspace's pixel-spectra plots gets an "x" at
its pixel, in the curve's colour, on every viewport (the images are assumed
co-registered); the marks follow Collect/Replace mode and vanish with their
curves. A full redraw on every change keeps this simple — there are only
ever a handful of markers.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

import numpy as np
from psygnal import SignalInstance
from PyQt6.QtCore import QObject, QPointF
from PyQt6.QtGui import QColor

from varda.image_rendering.raster_view.viewport_protocol import PointOverlayHandle
from varda.plotting.pixel_spectra_plot import PixelSpectraPlotWidget
from varda.workspaces.pixel_spectra_docks import PixelSpectraDocks


class MarkerViewport(Protocol):
    # Fires when the viewport's local coordinates move (it shows a region of
    # the image and was panned), so markers must be re-mapped.
    sigImageChanged: SignalInstance

    def pixelToLocalCoords(self, pixelCoords: np.ndarray) -> np.ndarray: ...

    def addPointOverlay(self, pos: QPointF, color: QColor) -> PointOverlayHandle: ...


class PixelMarkerController(QObject):
    def __init__(
        self,
        docks: PixelSpectraDocks,
        viewports: Sequence[MarkerViewport],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._docks = docks
        self._viewports = list(viewports)
        self._markers: list[PointOverlayHandle] = []
        for plot in docks.plots:
            self._watch(plot)
        docks.sigPlotAdded.connect(self._watch)
        for viewport in self._viewports:
            viewport.sigImageChanged.connect(self.refresh)

    def _watch(self, plot: PixelSpectraPlotWidget) -> None:
        plot.sigPixelCurvesChanged.connect(self.refresh)
        self.refresh()

    def refresh(self) -> None:
        for marker in self._markers:
            marker.remove()
        self._markers.clear()
        for plot in self._docks.plots:
            for curve in plot.pixelCurves:
                origin = plot.pixelOrigins.get(curve)
                if origin is None:
                    continue
                color = curve.config.color.value
                centre = np.array([[origin.x + 0.5, origin.y + 0.5]], dtype=float)
                for viewport in self._viewports:
                    (local,) = viewport.pixelToLocalCoords(centre)
                    self._markers.append(
                        viewport.addPointOverlay(
                            QPointF(float(local[0]), float(local[1])), color
                        )
                    )
