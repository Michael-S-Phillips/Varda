"""Ratio Explorer: box-ratio spectra from viewport clicks, plotted like pixel spectra.

The RatioExplorerTool reports a numerator and a denominator box; this
controller turns them into a ratio spectrum on the workspace's pixel plot,
places the denominator on the numerator's sensor column when column lock is
on, and can save the pair as ROIs so a promising spot is not lost.
"""

from __future__ import annotations

import functools
from collections.abc import Callable, Sequence
from typing import Protocol

import numpy as np
from PyQt6.QtCore import QObject, QPointF
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QLabel
from shapely.geometry import Polygon

from varda.common.entities import Color, ROIMode, VardaRaster
from varda.common.parameter import IntParameter, ParameterGroup
from varda.common.ui import ButtonBuilder, SectionBox, VBoxBuilder
from varda.image_loading.crism_geometry import (
    computeColumnLockedTranslation,
    loadColumnGeometry,
)
from varda.image_rendering.raster_view.viewport_protocol import ROIOverlayHandle
from varda.image_rendering.raster_view.viewport_tools.ratio_explorer_tool import (
    DENOMINATOR_COLOR,
    NUMERATOR_COLOR,
    RatioExplorerTool,
    RatioSelection,
    boxSize,
)
from varda.plotting.plot import VardaPlotWidget
from varda.rois.ratio import computeRatioSpectrum
from varda.rois.region_statistics import boxPolygonPixels, computeRegionStatistics
from varda.rois.roi_collection import ROICollection

NUMERATOR_ROI_COLOR = Color(0.0, 0.86, 0.0, 0.5)
DENOMINATOR_ROI_COLOR = Color(1.0, 0.0, 1.0, 0.5)


class RatioExplorerConfig(ParameterGroup):
    boxWidth = IntParameter(
        "Box Width", 5, range=(1, 99), units="px", description="Width of both boxes"
    )
    boxHeight = IntParameter(
        "Box Height", 5, range=(1, 99), units="px", description="Height of both boxes"
    )


class SpectrumSink(Protocol):
    def addSpectra(self, entries: Sequence[tuple]): ...


class MirrorViewport(Protocol):
    """The part of a viewport needed to show a box on it."""

    def pixelToLocalCoords(self, pixelCoords: np.ndarray) -> np.ndarray: ...

    def addROIOverlay(
        self, points: Sequence[QPointF], color: QColor
    ) -> ROIOverlayHandle: ...


class DenominatorOwner(Protocol):
    """The ROI manager's part in this: the column-lock toggle and the denominator."""

    @property
    def lockColumn(self) -> bool: ...

    def setDenominator(self, fid: int | None) -> None: ...


class RatioExplorerController(QObject):
    def __init__(
        self,
        collection: ROICollection,
        roiManager: DenominatorOwner,
        docks: SpectrumSink,
        config: RatioExplorerConfig,
        parent: QObject | None = None,
        *,
        imagesFor: Callable[[VardaRaster], Sequence[VardaRaster]] | None = None,
        labelWithImageName: bool = False,
    ) -> None:
        """``imagesFor(clickedImage)`` names the image(s) a selection is measured
        on (default: the clicked image itself); a workspace with co-registered
        images uses it to apply its Spectrum Source setting."""
        super().__init__(parent)
        self.config = config
        self._collection = collection
        self._roiManager = roiManager
        self._docks = docks
        self._imagesFor = imagesFor or (lambda clicked: [clicked])
        self._labelWithImageName = labelWithImageName
        self._current: tuple[VardaRaster, RatioSelection] | None = None
        self._saveCount = 0
        self._mirrorViewports: list[MirrorViewport] = []
        # per mirrored viewport: (numerator overlay, denominator overlay)
        self._mirrors: dict[int, list[ROIOverlayHandle | None]] = {}

    def setMirrorViewports(self, viewports: Sequence[MirrorViewport]) -> None:
        """Viewports that should also show the boxes (the images are assumed
        co-registered). The tool's own viewport draws its own and is skipped."""
        self._clearMirrors()
        self._mirrorViewports = list(viewports)

    def bindTool(self, tool: RatioExplorerTool) -> None:
        """Drive a freshly activated tool: box size, placement, plotting, saving."""
        image = tool.viewport.imageEntity
        tool.setBoxSizeProvider(
            lambda: (int(self.config.boxWidth.value), int(self.config.boxHeight.value))
        )
        tool.setDenominatorPlacer(functools.partial(self._placeDenominator, image))
        tool.sigSelectionChanged.connect(functools.partial(self._onSelection, image))
        tool.sigSelectionChanged.connect(
            functools.partial(self._mirrorSelection, tool.viewport)
        )
        tool.sigDeactivated.connect(self._clearMirrors)
        tool.sigSaveRequested.connect(self.saveCurrentBoxes)

    def _mirrorSelection(self, ownViewport: object, selection: RatioSelection) -> None:
        for viewport in self._mirrorViewports:
            if viewport is ownViewport:
                continue
            handles = self._mirrors.setdefault(id(viewport), [None, None])
            boxes = (
                (selection.numerator, NUMERATOR_COLOR),
                (selection.denominator, DENOMINATOR_COLOR),
            )
            for i, (polygon, color) in enumerate(boxes):
                handles[i] = _drawMirroredBox(viewport, handles[i], polygon, color)

    def _clearMirrors(self) -> None:
        for handles in self._mirrors.values():
            for handle in handles:
                if handle is not None:
                    handle.remove()
        self._mirrors.clear()

    def createSidebarSection(self) -> SectionBox:
        hint = QLabel("Left-click: numerator · Right-click: denominator · S: save")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: palette(mid);")
        return SectionBox(
            "Ratio Explorer",
            VBoxBuilder()
            .withWidget(self.config.createWidget())
            .withWidget(
                ButtonBuilder("Save Boxes as ROIs").onClick(self.saveCurrentBoxes)
            )
            .withWidget(hint),
        )

    def saveCurrentBoxes(self) -> None:
        """Add the current numerator/denominator boxes to the ROI collection and
        make the denominator the ratio reference, so the pair can be re-plotted."""
        if self._current is None:
            return
        image, selection = self._current
        if selection.numerator is None or selection.denominator is None:
            return
        self._saveCount += 1
        n = self._saveCount
        self._collection.addROI(
            self._geometryFor(image, selection.numerator),
            f"Ratio {n} numerator",
            NUMERATOR_ROI_COLOR,
            ROIMode.RECTANGLE,
        )
        denominatorFid = self._collection.addROI(
            self._geometryFor(image, selection.denominator),
            f"Ratio {n} denominator",
            DENOMINATOR_ROI_COLOR,
            ROIMode.RECTANGLE,
        )
        self._roiManager.setDenominator(denominatorFid)

    def _placeDenominator(
        self, image: VardaRaster, numerator: np.ndarray, row: int, col: int
    ) -> np.ndarray:
        """Same-size box at the click; on the numerator's sensor column if locked."""
        fallback = boxPolygonPixels(col, row, *boxSize(numerator))
        if not self._roiManager.lockColumn or not image.filePath:
            return fallback
        geometry = loadColumnGeometry(image.filePath)
        if geometry is None:
            return fallback
        shift = computeColumnLockedTranslation(
            numerator, clickRow=row, clickCol=col, geometry=geometry
        )
        return fallback if shift is None else numerator + np.array(shift)

    def _onSelection(self, image: VardaRaster, selection: RatioSelection) -> None:
        self._current = (image, selection)
        if selection.numerator is None or selection.denominator is None:
            return
        entries = []
        for source in self._imagesFor(image):
            numerator = np.asarray(
                computeRegionStatistics(selection.numerator, source)["mean"]
            )
            denominator = np.asarray(
                computeRegionStatistics(selection.denominator, source)["mean"]
            )
            ratio = computeRatioSpectrum(numerator, denominator)
            wavelengths = VardaPlotWidget.getPlottableWavelengths(source, len(ratio))
            entries.append((wavelengths, ratio, self._label(source, selection)))
        # one batch, so Replace mode keeps every image of this selection
        self._docks.addSpectra(entries)

    def _label(self, image: VardaRaster, selection: RatioSelection) -> str:
        assert selection.numerator is not None and selection.denominator is not None
        nc, nr = _centerPixel(selection.numerator)
        dc, dr = _centerPixel(selection.denominator)
        boxes = f"({nc}, {nr}) / ({dc}, {dr})"
        if self._labelWithImageName:
            return f"{image.name} ratio {boxes}"
        return f"Ratio {boxes}"

    @staticmethod
    def _geometryFor(image: VardaRaster, pixels: np.ndarray) -> Polygon:
        if image.hasGeospatialData:
            return Polygon(
                [image.pixelToGeo(int(round(c)), int(round(r))) for c, r in pixels]
            )
        return Polygon(pixels)


def _drawMirroredBox(
    viewport: MirrorViewport,
    handle: ROIOverlayHandle | None,
    polygon: np.ndarray | None,
    color: QColor,
) -> ROIOverlayHandle | None:
    if polygon is None:
        if handle is not None:
            handle.remove()
        return None
    points = [
        QPointF(float(c), float(r)) for c, r in viewport.pixelToLocalCoords(polygon)
    ]
    if handle is None:
        return viewport.addROIOverlay(points, color)
    handle.setPoints(points)
    return handle


def _centerPixel(polygon: np.ndarray) -> tuple[int, int]:
    """The pixel a ``boxPolygonPixels`` box was centred on (inverse of that function)."""
    width, height = boxSize(polygon)
    return int(polygon[0, 0]) + (width - 1) // 2, int(polygon[0, 1]) + (height - 1) // 2
