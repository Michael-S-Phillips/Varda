"""The find-data map: footprints in longitude and latitude (equirectangular),
over a graticule, a basemap image and vector overlays, with a box to search
in. Clicking selects the footprints under the pointer."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pyqtgraph as pg
import shapely
from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from varda.catalogs.catalog import Product

FOOTPRINT_PEN = pg.mkPen("#38c8ff", width=1)
SELECTED_PEN = pg.mkPen("#ffd200", width=2.5)
AREA_PEN = pg.mkPen("#ff4fd8", width=2, style=Qt.PenStyle.DashLine)
OVERLAY_COLORS = ("#7CFC00", "#ff8c00", "#ff4040", "#c080ff", "#ffffff")

Bounds = tuple[float, float, float, float]  # west, south, east, north


def outlines(geometries: Sequence[shapely.Geometry]) -> tuple[np.ndarray, np.ndarray]:
    """Every polygon ring and line as one x, y pair of arrays, with NaN
    between pieces (so one curve item draws them all)."""
    xs, ys = [], []
    for geometry in geometries:
        for part in getattr(geometry, "geoms", [geometry]):
            rings = (
                [part.exterior, *part.interiors]
                if isinstance(part, shapely.Polygon)
                else [part]
                if isinstance(part, shapely.LineString)
                else []
            )
            for ring in rings:
                coords = np.asarray(ring.coords)
                if len(coords):
                    xs += [coords[:, 0], [np.nan]]
                    ys += [coords[:, 1], [np.nan]]
    if not xs:
        return np.zeros(0), np.zeros(0)
    return np.concatenate(xs), np.concatenate(ys)


class FootprintMap(QWidget):
    sigClicked = pyqtSignal(float, float, bool)  # longitude, latitude, add to selection

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.plot = pg.PlotWidget()
        self.plot.setAspectLocked(True)
        self.plot.showGrid(x=True, y=True, alpha=0.25)
        self.plot.setLabel("bottom", "Longitude (°E)")
        self.plot.setLabel("left", "Latitude (°)")
        self.basemapItem = pg.ImageItem()
        self.basemapItem.setZValue(-10)
        self.plot.addItem(self.basemapItem)
        self.footprints = pg.PlotCurveItem(pen=FOOTPRINT_PEN, connect="finite")
        self.selected = pg.PlotCurveItem(pen=SELECTED_PEN, connect="finite")
        self.selected.setZValue(5)
        self.plot.addItem(self.footprints)
        self.plot.addItem(self.selected)
        self.area = pg.RectROI(
            [0, 0], [1, 1], pen=AREA_PEN, movable=True, resizable=True
        )
        self.area.setVisible(False)
        self.plot.addItem(self.area)
        self._overlays: list[pg.GraphicsObject] = []
        self.plot.scene().sigMouseClicked.connect(self._onClick)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.plot)
        self.showWhole()

    def showWhole(self) -> None:
        self.plot.getViewBox().setRange(
            xRange=(-180, 180), yRange=(-90, 90), padding=0.02
        )

    def zoomTo(self, bounds: Bounds, padding: float = 0.15) -> None:
        west, south, east, north = bounds
        self.plot.getViewBox().setRange(
            xRange=(west, east), yRange=(south, north), padding=padding
        )

    def viewBounds(self) -> Bounds:
        (west, east), (south, north) = self.plot.getViewBox().viewRange()
        return (
            max(west, -180.0),
            max(south, -90.0),
            min(east, 180.0),
            min(north, 90.0),
        )

    # --- the search box ---------------------------------------------------------------

    def showArea(self, visible: bool) -> None:
        if visible and not self.area.isVisible():
            west, south, east, north = self.viewBounds()
            width, height = east - west, north - south
            self.area.setPos((west + width / 4, south + height / 4))
            self.area.setSize((width / 2, height / 2))
        self.area.setVisible(visible)

    def areaBounds(self) -> Bounds:
        x, y = self.area.pos()
        width, height = self.area.size()
        return (float(x), float(y), float(x + width), float(y + height))

    def setArea(self, bounds: Bounds) -> None:
        west, south, east, north = bounds
        self.area.setPos((west, south))
        self.area.setSize((east - west, north - south))

    # --- layers ------------------------------------------------------------------------

    def setFootprints(self, products: Sequence[Product]) -> None:
        x, y = outlines([p.footprint for p in products])
        self.footprints.setData(x, y)

    def setSelected(self, products: Sequence[Product]) -> None:
        x, y = outlines([p.footprint for p in products])
        self.selected.setData(x, y)

    def setBasemap(self, rgba: np.ndarray | None, bounds: Bounds | None = None) -> None:
        if rgba is None or bounds is None:
            self.basemapItem.clear()
            return
        west, south, east, north = bounds
        # rows run north to south; the plot's y runs up
        self.basemapItem.setImage(rgba[::-1].transpose(1, 0, 2), autoLevels=False)
        self.basemapItem.setRect(QRectF(west, south, east - west, north - south))

    def addOverlay(self, geometries: Sequence[shapely.Geometry]) -> None:
        color = OVERLAY_COLORS[len(self._overlays) % len(OVERLAY_COLORS)]
        x, y = outlines(geometries)
        points = [
            g for g in geometries if isinstance(g, (shapely.Point, shapely.MultiPoint))
        ]
        item = pg.PlotCurveItem(x, y, pen=pg.mkPen(color, width=2), connect="finite")
        item.setZValue(3)
        self.plot.addItem(item)
        self._overlays.append(item)
        if points:
            coords = np.array([c for g in points for c in shapely.get_coordinates(g)])
            scatter = pg.ScatterPlotItem(
                coords[:, 0], coords[:, 1], size=5, brush=pg.mkBrush(color), pen=None
            )
            scatter.setZValue(3)
            self.plot.addItem(scatter)
            self._overlays.append(scatter)

    def clearOverlays(self) -> None:
        for item in self._overlays:
            self.plot.removeItem(item)
        self._overlays = []

    def _onClick(self, event) -> None:
        if event.button() != Qt.MouseButton.LeftButton or event.double():
            return
        point: QPointF = self.plot.getViewBox().mapSceneToView(event.scenePos())
        add = bool(
            event.modifiers()
            & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
        )
        self.sigClicked.emit(point.x(), point.y(), add)
