"""The Subset (crop) dialog's preview: the image with a box to drag or
resize over the part to keep, the box's mean spectrum, and ranges to drag
on that spectrum over the bands to keep. Box and ranges follow the typed
rows, columns and bands, and set them."""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import QPointF, QRectF, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from varda.common.entities import VardaRaster
from varda.common.ui import MutedLabel
from varda.image_rendering.image_renderer import ImageRenderer

if TYPE_CHECKING:  # geometry imports this module for its preview
    from varda.analysis.geometry import SubsetAnalysis

SPECTRUM_PIXELS = 4096  # pixels of the box averaged for its spectrum, at most
BOX_PEN = pg.mkPen("#ffd400", width=2)
SPAN_BRUSH = (255, 212, 0, 45)


def runs(indices: list[int]) -> list[tuple[int, int]]:
    """Sorted band indices as (first, last) runs of neighbors."""
    found: list[tuple[int, int]] = []
    for index in sorted(indices):
        if found and index == found[-1][1] + 1:
            found[-1] = (found[-1][0], index)
        else:
            found.append((index, index))
    return found


class SpanItem(pg.LinearRegionItem):
    """A range of bands; double-click removes it."""

    sigRemoveRequested = pyqtSignal(object)

    def mouseDoubleClickEvent(self, event):  # noqa: N802 (Qt's name)
        self.sigRemoveRequested.emit(self)
        event.accept()


class CropPreview(QWidget):
    def __init__(
        self,
        image: VardaRaster,
        analysis: SubsetAnalysis,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.image, self.analysis = image, analysis
        self._syncing = False
        model = image.bandModel
        self.axis = (
            model.native(model.centers)
            if model.centers is not None
            else np.arange(1, image.bandCount + 1, dtype=np.float64)
        )
        self.badBands = (
            model.badBands
            if model.badBands.size == image.bandCount
            else np.zeros(image.bandCount, bool)
        )
        self.axisLabel = (
            f"Wavelength ({model.label})" if model.centers is not None else "Band"
        )

        # the image, with the box
        self.view = pg.GraphicsLayoutWidget()
        viewBox = self.view.addViewBox(lockAspect=True, invertY=True)
        viewBox.addItem(pg.ImageItem(np.asarray(ImageRenderer(image=image).render())))
        self.box = pg.RectROI(
            [0, 0],
            [image.width, image.height],
            pen=BOX_PEN,
            maxBounds=QRectF(0, 0, image.width, image.height),
            translateSnap=True,
            scaleSnap=True,
            snapSize=1.0,
        )
        self.box.addScaleHandle([0, 0], [1, 1])
        self.box.sigRegionChangeFinished.connect(self._onBox)
        viewBox.addItem(self.box)

        # the box's mean spectrum, with the band ranges
        self.plot = pg.PlotWidget()
        self.plot.setLabel("bottom", self.axisLabel)
        self.plot.showGrid(x=True, y=True, alpha=0.2)
        self.curve = self.plot.plot(pen=pg.mkPen("w", width=1.5))
        self.spans: list[SpanItem] = []
        addRange = QPushButton("Add Range")
        addRange.setToolTip("Another range of bands to keep")
        addRange.clicked.connect(self.addRange)
        keepAll = QPushButton("Keep All Bands")
        keepAll.clicked.connect(self.keepAll)
        buttons = QHBoxLayout()
        buttons.addWidget(
            MutedLabel(
                "Drag the box over the part to keep, and the ranges over the "
                "bands to keep (double-click a range to remove it)."
            ),
            1,
        )
        buttons.addWidget(addRange)
        buttons.addWidget(keepAll)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view, 3)
        layout.addWidget(self.plot, 2)
        layout.addLayout(buttons)
        self.setMinimumHeight(420)

        analysis.sigParameterChanged.connect(self._onSettings)
        self._showSettings()

    # --- rows and columns ---------------------------------------------------------

    def _window(self) -> tuple[int, int, int, int]:
        """(top, left, height, width) from the settings, 0-based."""
        a = self.analysis
        top, left = int(a.firstRow.value) - 1, int(a.firstColumn.value) - 1
        height = int(a.lastRow.value) - top
        width = int(a.lastColumn.value) - left
        return top, left, max(height, 1), max(width, 1)

    def _onBox(self, _box=None) -> None:
        if self._syncing:
            return
        x, y = (int(round(v)) for v in self.box.pos())
        width, height = (max(int(round(v)), 1) for v in self.box.size())
        self._syncing = True
        try:
            a = self.analysis
            a.firstRow.set(y + 1)
            a.lastRow.set(min(y + height, self.image.height))
            a.firstColumn.set(x + 1)
            a.lastColumn.set(min(x + width, self.image.width))
        finally:
            self._syncing = False
        self._showSpectrum()

    # --- bands ------------------------------------------------------------------------

    def _spanEdges(self, first: int, last: int) -> tuple[float, float]:
        """A run of bands as a range on the spectrum's axis, from halfway to
        the band before to halfway to the band after."""
        axis = self.axis
        step = float(np.median(np.abs(np.diff(axis)))) if axis.size > 1 else 1.0
        low = axis[first] - step / 2
        high = axis[last] + step / 2
        return float(min(low, high)), float(max(low, high))

    def _addSpan(self, low: float, high: float) -> SpanItem:
        span = SpanItem(values=(low, high), brush=SPAN_BRUSH, swapMode="sort")
        span.setToolTip("Bands to keep; drag the edges, double-click to remove")
        span.sigRegionChangeFinished.connect(lambda _: self._onSpans())
        span.sigRemoveRequested.connect(self.removeSpan)
        self.plot.addItem(span)
        self.spans.append(span)
        return span

    def _clearSpans(self) -> None:
        for span in self.spans:
            self.plot.removeItem(span)
        self.spans = []

    def addRange(self) -> None:
        low, high = float(self.axis.min()), float(self.axis.max())
        middle, width = (low + high) / 2, (high - low) / 10
        self._addSpan(middle - width / 2, middle + width / 2)
        self._onSpans()

    def removeSpan(self, span: SpanItem) -> None:
        if span in self.spans:
            self.plot.removeItem(span)
            self.spans.remove(span)
            self._onSpans()

    def keepAll(self) -> None:
        self.analysis.bands.set("")

    def _onSpans(self) -> None:
        """The bands inside any range, written as the Bands setting."""
        inside = np.zeros(self.axis.size, bool)
        for span in self.spans:
            low, high = span.getRegion()
            inside |= (self.axis >= low) & (self.axis <= high)
        everything = bool(inside.all())
        text = ", ".join(
            f"{a + 1}" if a == b else f"{a + 1}-{b + 1}"
            for a, b in runs(list(np.flatnonzero(inside)))
        )
        self._syncing = True
        try:
            self.analysis.bands.set("" if everything else text)
        finally:
            self._syncing = False

    # --- from the settings -------------------------------------------------------------

    def _onSettings(self, *_) -> None:
        if not self._syncing:
            self._showSettings()
        else:
            self._showSpectrum()

    def _showSettings(self) -> None:
        top, left, height, width = self._window()
        self._syncing = True
        try:
            self.box.setPos(QPointF(left, top), finish=False)
            self.box.setSize(QPointF(width, height), finish=False)
            self._clearSpans()
            for first, last in runs(self.analysis.bandList(self.image)):
                self._addSpan(*self._spanEdges(first, last))
        finally:
            self._syncing = False
        self._showSpectrum()

    def _showSpectrum(self) -> None:
        """The box's mean spectrum (of up to SPECTRUM_PIXELS of its pixels)."""
        top, left, height, width = self._window()
        height = min(height, self.image.height - top)
        width = min(width, self.image.width - left)
        if height < 1 or width < 1:
            self.curve.setData([], [])
            return
        stride = max(1, int(np.ceil(np.sqrt(height * width / SPECTRUM_PIXELS))))
        raw = self.image.getData(window=(top, left, height, width))
        block = np.ma.filled(np.ma.asarray(raw, dtype=np.float64), np.nan)
        block = block[::stride, ::stride].reshape(-1, self.image.bandCount)
        nodata = self.image.bandModel.noData
        if nodata is not None:
            block[block == nodata] = np.nan
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)  # bands with no values
            mean = np.nanmean(block, axis=0)
        mean[self.badBands] = np.nan
        self.curve.setData(self.axis, mean, connect="finite")
