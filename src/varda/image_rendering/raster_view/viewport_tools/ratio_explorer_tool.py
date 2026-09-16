"""Ratio Explorer: quick numerator/denominator box ratios by clicking."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, override

import attrs
import numpy as np
from PyQt6.QtCore import QPointF, Qt, pyqtSignal
from PyQt6.QtGui import QColor

from varda.image_rendering.raster_view.image_viewport import ImageViewport
from varda.image_rendering.raster_view.pointer_event import (
    KeyEvent,
    PointerAction,
    PointerEvent,
)
from varda.image_rendering.raster_view.viewport_tools.viewport_tool import ViewportTool
from varda.rois.region_statistics import boxPolygonPixels

if TYPE_CHECKING:
    from varda.image_rendering.raster_view.viewport_protocol import ROIOverlayHandle

NUMERATOR_COLOR = QColor(0, 220, 0)
DENOMINATOR_COLOR = QColor(255, 0, 255)

# (numerator polygon, clicked row, clicked col) -> denominator polygon
DenominatorPlacer = Callable[[np.ndarray, int, int], np.ndarray]


@attrs.frozen
class RatioSelection:
    """The current boxes as (4, 2) (col, row) pixel-corner polygons, or None."""

    numerator: np.ndarray | None
    denominator: np.ndarray | None


def boxSize(polygon: np.ndarray) -> tuple[int, int]:
    """(width, height) in pixels of a box polygon from ``boxPolygonPixels``."""
    return int(polygon[1, 0] - polygon[0, 0]), int(polygon[2, 1] - polygon[1, 1])


class RatioExplorerTool(ViewportTool):
    """Left-click drops a numerator box, right-click a same-size denominator box.

    The tool only reports the boxes; the workspace computes and plots the
    ratio. Box size comes from a provider so a workspace setting applies
    without re-creating the tool, and denominator placement can be delegated
    (e.g. to lock it to the numerator's sensor column).
    """

    toolName = "Ratio Explorer"
    toolDescription = (
        "Left-click: numerator box, right-click: denominator box. "
        "S saves both as ROIs, Esc clears."
    )
    toolCategory = "Selection"

    sigSelectionChanged = pyqtSignal(object)  # RatioSelection
    sigSaveRequested = pyqtSignal()

    def __init__(self, viewport: ImageViewport, parent=None):
        super().__init__(viewport, parent)
        self._boxSize: Callable[[], tuple[int, int]] = lambda: (5, 5)
        self._placeDenominator: DenominatorPlacer | None = None
        self.selection = RatioSelection(None, None)
        self._numeratorOverlay: ROIOverlayHandle | None = None
        self._denominatorOverlay: ROIOverlayHandle | None = None

    def setBoxSizeProvider(self, provider: Callable[[], tuple[int, int]]) -> None:
        self._boxSize = provider

    def setDenominatorPlacer(self, placer: DenominatorPlacer | None) -> None:
        self._placeDenominator = placer

    def activate(self):
        super().activate()
        self.showText(self.toolDescription, timeout=4000)

    def deactivate(self):
        self._numeratorOverlay = self._drawBox(
            self._numeratorOverlay, None, NUMERATOR_COLOR
        )
        self._denominatorOverlay = self._drawBox(
            self._denominatorOverlay, None, DENOMINATOR_COLOR
        )
        super().deactivate()

    @override
    def onPointerEvent(self, event: PointerEvent) -> bool:
        if event.button not in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton):
            return False
        if event.action == PointerAction.RELEASE:
            return True  # consumed: the press already acted
        if event.action != PointerAction.PRESS:
            return False

        col, row = int(event.imagePos.x()), int(event.imagePos.y())
        if event.button == Qt.MouseButton.LeftButton:
            width, height = self._boxSize()
            self._setSelection(
                boxPolygonPixels(col, row, width, height), self.selection.denominator
            )
            return True

        numerator = self.selection.numerator
        if numerator is None:
            self.showText("Left-click a numerator box first", timeout=2000)
            return True
        if self._placeDenominator is not None:
            denominator = self._placeDenominator(numerator, row, col)
        else:
            denominator = boxPolygonPixels(col, row, *boxSize(numerator))
        self._setSelection(numerator, denominator)
        return True

    @override
    def onKeyEvent(self, event: KeyEvent) -> bool:
        key = event.key.value if isinstance(event.key, Qt.Key) else event.key
        if key == Qt.Key.Key_S.value:
            self.sigSaveRequested.emit()
            return True
        if key == Qt.Key.Key_Escape.value:
            self._setSelection(None, None)
            return True
        return False

    def _setSelection(
        self, numerator: np.ndarray | None, denominator: np.ndarray | None
    ) -> None:
        self.selection = RatioSelection(numerator, denominator)
        self._numeratorOverlay = self._drawBox(
            self._numeratorOverlay, numerator, NUMERATOR_COLOR
        )
        self._denominatorOverlay = self._drawBox(
            self._denominatorOverlay, denominator, DENOMINATOR_COLOR
        )
        self.sigSelectionChanged.emit(self.selection)

    def _drawBox(
        self,
        handle: ROIOverlayHandle | None,
        polygon: np.ndarray | None,
        color: QColor,
    ) -> ROIOverlayHandle | None:
        if polygon is None:
            if handle is not None:
                handle.remove()
            return None
        points = [
            QPointF(float(c), float(r))
            for c, r in self.viewport.pixelToLocalCoords(polygon)
        ]
        if handle is None:
            return self.viewport.addROIOverlay(points, color)
        handle.setPoints(points)
        return handle
