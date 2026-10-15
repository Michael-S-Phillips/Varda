"""Mark every plotted pixel spectrum on the image(s) it came from.

Each pixel curve on any of a workspace's pixel-spectra plots is marked at
its pixel in the curve's color, on every viewport (the images are assumed
co-registered): a circle for a single pixel, the window's outline for a
region's mean spectrum. The marker of the curve selected on a plot is
highlighted. Marks follow Collect/Replace mode and vanish with their curves.
A full redraw on every change keeps this simple: there are only ever a
handful of markers.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

import numpy as np
from psygnal import SignalInstance
from PyQt6.QtCore import QObject, QPointF
from PyQt6.QtGui import QColor

from varda.image_rendering.raster_view.viewport_protocol import (
    PointOverlayHandle,
    ROIOverlayHandle,
)
from varda.plotting.pixel_spectra_plot import PixelOrigin, PixelSpectraPlotWidget
from varda.workspaces.pixel_spectra_docks import PixelSpectraDocks


REGION_FILL_ALPHA = 40


class MarkerViewport(Protocol):
    # Fires when the viewport's local coordinates move (it shows a region of
    # the image and was panned), so markers must be re-mapped.
    sigImageChanged: SignalInstance

    def pixelToLocalCoords(self, pixelCoords: np.ndarray) -> np.ndarray: ...

    def addPointOverlay(
        self, pos: QPointF, color: QColor, symbol: str = "x"
    ) -> PointOverlayHandle: ...

    def addROIOverlay(
        self, points: Sequence[QPointF], color: QColor
    ) -> ROIOverlayHandle: ...


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
        self._markers: list[PointOverlayHandle | ROIOverlayHandle] = []
        for plot in docks.plots:
            self._watch(plot)
        docks.sigPlotAdded.connect(self._watch)
        for viewport in self._viewports:
            viewport.sigImageChanged.connect(self.refresh)

    def _watch(self, plot: PixelSpectraPlotWidget) -> None:
        plot.sigPixelCurvesChanged.connect(self.refresh)
        # A bound method (not a lambda): Qt drops it when this controller goes,
        # so a plot deselecting as it's torn down can't reach dead viewports
        plot.sigSelectedCurveChanged.connect(self._onSelectionChanged)
        self.refresh()

    def _onSelectionChanged(self, _curve) -> None:
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
                color = curve.config.color.value.toQColor()
                for viewport in self._viewports:
                    marker = self._mark(viewport, origin, color)
                    marker.setHighlighted(curve is plot.selectedCurve)
                    self._markers.append(marker)

    @staticmethod
    def _mark(
        viewport: MarkerViewport, origin: PixelOrigin, color: QColor
    ) -> PointOverlayHandle | ROIOverlayHandle:
        if origin.width == origin.height == 1:
            centre = np.array([[origin.x + 0.5, origin.y + 0.5]], dtype=float)
            (local,) = viewport.pixelToLocalCoords(centre)
            return viewport.addPointOverlay(
                QPointF(float(local[0]), float(local[1])), color, symbol="o"
            )
        corners = viewport.pixelToLocalCoords(origin.corners())
        translucent = QColor(
            color
        )  # the outline stays opaque; the fill shows the image
        translucent.setAlpha(REGION_FILL_ALPHA)
        return viewport.addROIOverlay(
            [QPointF(float(x), float(y)) for x, y in corners], translucent
        )
