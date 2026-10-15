"""The mosaic workspace's views: the mosaic preview on map coordinates, and
an image view for placing tie points on one input. Both draw with pyqtgraph
directly, so a preview that's re-rendered (as images move) keeps the zoom."""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import QPointF, Qt, pyqtSignal
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from varda.common.entities import VardaRaster
from varda.mosaicking.grid import TargetGrid
from varda.mosaicking.recipe import Seam

PREVIEW_PIXELS = 1500  # the preview's longest side, at most
FOOTPRINT_PEN = pg.mkPen("#ffd200", width=2)
SEAM_PEN = pg.mkPen("#ff4fd8", width=2, style=Qt.PenStyle.DashLine)
SEAM_EDIT_PEN = pg.mkPen("#ff4fd8", width=2)


def displayBands(image: VardaRaster) -> list[int]:
    """The bands shown in previews: the image's three display bands, or its one band."""
    if image.bandCount >= 3:
        return [int(b) for b in np.asarray(image.defaultBands).ravel()[:3]]
    return [0]


def toRgba(cube: np.ndarray) -> np.ndarray:
    """(rows, cols, 1 or 3) values to RGBA bytes, each channel stretched over
    its 2-98 % range; pixels with no data are transparent."""
    finite = np.isfinite(cube).all(axis=2)
    channels = []
    for k in range(cube.shape[2]):
        band = cube[:, :, k]
        values = band[np.isfinite(band)]
        lo, hi = np.percentile(values, [2, 98]) if values.size else (0.0, 1.0)
        scaled = np.clip((band - lo) / ((hi - lo) or 1.0), 0, 1)
        channels.append(np.nan_to_num(scaled) * 255)
    rgb = channels * 3 if len(channels) == 1 else channels
    alpha = np.where(finite, 255, 0)
    return np.stack([*rgb, alpha], axis=-1).astype(np.uint8)


def downsampled(
    image: VardaRaster, bands: list[int], maxPixels: int
) -> tuple[np.ndarray, int]:
    """The image's ``bands`` read every ``step``-th pixel so the longest side
    is at most ``maxPixels``; returns the cube and the step."""
    step = max(1, int(np.ceil(max(image.width, image.height) / maxPixels)))
    data = np.ma.filled(
        np.ma.asarray(image.getData(bandIndices=bands), dtype=np.float32), np.nan
    )
    if image.nodata is not None:
        data[data == image.nodata] = np.nan
    return data[::step, ::step], step


class MapAxis(pg.AxisItem):
    """Map coordinates as plain numbers (pyqtgraph writes 3.9995e+06)."""

    def tickStrings(self, values, scale, spacing) -> list[str]:
        decimals = max(0, -int(np.floor(np.log10(spacing * scale)))) if spacing else 0
        return [f"{value * scale:.{decimals}f}" for value in values]


MANUAL_COLOR = "#ffd200"
AUTO_COLOR = "#38c8ff"
OUTLIER_COLOR = "#ff4040"


class _PlotView(QWidget):
    def __init__(
        self,
        parent: QWidget | None = None,
        axisItems: dict[str, pg.AxisItem] | None = None,
    ):
        super().__init__(parent)
        self.plot = pg.PlotWidget(axisItems=axisItems)
        self.plot.setAspectLocked(True)
        self.plot.showGrid(x=False, y=False)
        self.imageItem = pg.ImageItem()
        self.plot.addItem(self.imageItem)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.plot)


class MosaicCanvas(_PlotView):
    """The mosaic preview, in map coordinates (north up), with the selected
    input's footprint outlined. Arrow keys ask to nudge the selected input
    (Shift for ten times as far)."""

    sigNudge = pyqtSignal(int, int)  # (right, up) steps, in output pixels
    # (seam index, region index, new outline (N, 2) in map coordinates)
    sigSeamEdited = pyqtSignal(int, int, object)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(
            parent,
            axisItems={"bottom": MapAxis("bottom"), "left": MapAxis("left")},
        )
        self.plot.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.plot.keyPressEvent = self._keyPress  # type: ignore[method-assign]
        self.footprint = pg.PlotDataItem(pen=FOOTPRINT_PEN)
        self.plot.addItem(self.footprint)
        self._seamItems: list[pg.GraphicsObject] = []
        self._framed = False

    def showPreview(self, cube: np.ndarray, grid: TargetGrid) -> None:
        """Show a rendered preview; the first one frames the view."""
        northUp = grid.transform.e < 0
        image = toRgba(cube[::-1] if northUp else cube)
        self.plot.getViewBox().invertY(not northUp)
        x0, y0 = grid.transform * (0, 0)
        x1, y1 = grid.transform * (grid.width, grid.height)
        self.imageItem.setImage(image, autoLevels=False)
        self.imageItem.setRect(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0))
        if not self._framed:
            self.plot.autoRange()
            self._framed = True

    def showFootprint(self, corners: np.ndarray | None) -> None:
        if corners is None:
            self.footprint.setData([], [])
            return
        closed = np.vstack([corners, corners[:1]])
        self.footprint.setData(closed[:, 0], closed[:, 1])

    def showSeams(self, seams: list[Seam], editable: bool = False) -> None:
        """Outline each seam's area (where the lower image takes over); when
        ``editable``, as polygons whose corners can be dragged."""
        for item in self._seamItems:
            self.plot.removeItem(item)
        self._seamItems = []
        for s, seam in enumerate(seams):
            for r, region in enumerate(seam.regions):
                if editable:
                    roi = pg.PolyLineROI(
                        [tuple(p) for p in region], closed=True, pen=SEAM_EDIT_PEN
                    )
                    roi.sigRegionChangeFinished.connect(
                        lambda roi, s=s, r=r: self._onSeamEdited(roi, s, r)
                    )
                    item: pg.GraphicsObject = roi
                else:
                    closed = np.vstack([region, region[:1]])
                    item = pg.PlotDataItem(closed[:, 0], closed[:, 1], pen=SEAM_PEN)
                self.plot.addItem(item)
                self._seamItems.append(item)

    def _onSeamEdited(self, roi: pg.PolyLineROI, seam: int, region: int) -> None:
        # Handles sit in the ROI's own coordinates; its parent is the plot's
        # view, which is in map coordinates
        corners = [roi.mapToParent(handle["pos"]) for handle in roi.handles]
        outline = np.array([[p.x(), p.y()] for p in corners], float)
        self.sigSeamEdited.emit(seam, region, outline)

    def _keyPress(self, event) -> None:
        step = 10 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1
        moves = {
            Qt.Key.Key_Left: (-step, 0),
            Qt.Key.Key_Right: (step, 0),
            Qt.Key.Key_Up: (0, step),
            Qt.Key.Key_Down: (0, -step),
        }
        if event.key() in moves:
            self.sigNudge.emit(*moves[event.key()])
            event.accept()
        else:
            pg.PlotWidget.keyPressEvent(self.plot, event)


class ImagePointView(_PlotView):
    """One input in its own pixel coordinates (rows down), for placing tie
    points: a click reports the full-resolution pixel position."""

    sigClicked = pyqtSignal(QPointF)  # (col, row) in the image's pixels

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.plot.getViewBox().invertY(True)
        self.markers = pg.ScatterPlotItem(
            size=12, pen=pg.mkPen(MANUAL_COLOR, width=2), brush=None
        )
        # Automatic points are many: small dots, red where the fit left them out
        self.autoMarkers = pg.ScatterPlotItem(size=5, pen=None)
        self.pending = pg.ScatterPlotItem(
            size=14, pen=pg.mkPen("#ff4040", width=2), brush=None, symbol="+"
        )
        self.plot.addItem(self.autoMarkers)
        self.plot.addItem(self.markers)
        self.plot.addItem(self.pending)
        self._labels: list[pg.TextItem] = []
        self.plot.scene().sigMouseClicked.connect(self._onClick)
        self.image: VardaRaster | None = None

    def setImage(self, image: VardaRaster | None) -> None:
        self.image = image
        if image is None:
            self.imageItem.clear()
            return
        cube, step = downsampled(image, displayBands(image), 1200)
        self.imageItem.setImage(toRgba(cube), autoLevels=False)
        self.imageItem.setRect(0, 0, cube.shape[1] * step, cube.shape[0] * step)
        self.plot.autoRange()

    def showPoints(
        self,
        points: list[tuple[float, float]],
        pending: tuple[float, float] | None = None,
        kinds: list[str] | None = None,
    ) -> None:
        """Mark tie points: ``kinds`` says which are "manual" (numbered, by
        their row in the table), "auto" or "outlier" (manual by default)."""
        kinds = kinds or ["manual"] * len(points)
        for label in self._labels:
            self.plot.removeItem(label)
        self._labels = []
        manual = [
            (n, p) for n, (p, k) in enumerate(zip(points, kinds), 1) if k == "manual"
        ]
        self.markers.setData(
            pos=[p for _, p in manual]
        ) if manual else self.markers.setData([], [])
        for number, (x, y) in manual:
            label = pg.TextItem(str(number), color=MANUAL_COLOR, anchor=(0, 1))
            label.setPos(x, y)
            self.plot.addItem(label)
            self._labels.append(label)
        auto = [(p, k) for p, k in zip(points, kinds) if k != "manual"]
        if auto:
            self.autoMarkers.setData(
                pos=[p for p, _ in auto],
                brush=[
                    pg.mkBrush(OUTLIER_COLOR if k == "outlier" else AUTO_COLOR)
                    for _, k in auto
                ],
            )
        else:
            self.autoMarkers.setData([], [])
        self.pending.setData(pos=[pending]) if pending else self.pending.setData([], [])

    def _onClick(self, event) -> None:
        if (
            self.image is None
            or event.button() != Qt.MouseButton.LeftButton
            or event.double()
        ):
            return
        point = self.plot.getViewBox().mapSceneToView(event.scenePos())
        if 0 <= point.x() < self.image.width and 0 <= point.y() < self.image.height:
            self.sigClicked.emit(QPointF(point.x(), point.y()))
