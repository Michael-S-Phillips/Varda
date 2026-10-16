"""Profiles plot: a band sampled along lines, against distance along them.

Each line is one curve in its color. Hovering reads out the distance and
value and reports where that is on the image (sigCursor), so the views can
mark it. For a DEM with distances in meters the vertical exaggeration is
shown. Export: CSV (every sample, with its pixel and map position), PNG, SVG
and PDF."""

from __future__ import annotations

import csv
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from varda.common.entities import VardaRaster
from varda.common.ui import MutedLabel
from varda.lines.line_collection import VardaLine
from varda.lines.profile import Profile, profile
from varda.plotting.plot_export import IMAGE_FILTER, exportImage

KM_FROM = 5000.0  # m: longer profiles are plotted in kilometers
EXPORT_FILTER = f"CSV data (*.csv);;{IMAGE_FILTER}"


def bandLabel(image: VardaRaster, band: int) -> str:
    names = list(image.bandNames or [])
    if band < len(names) and names[band]:
        return str(names[band])
    wavelengths = image.wavelengths
    if wavelengths is not None and band < len(wavelengths):
        return f"Band {band + 1} ({wavelengths[band]})"
    return f"Band {band + 1}"


class ProfilePlotWidget(QWidget):
    sigCursor = pyqtSignal(object)  # image px (2,) of the hovered sample, or None

    def __init__(self, image: VardaRaster, parent: QWidget | None = None):
        super().__init__(parent)
        self.image = image
        self.lines: list[VardaLine] = []
        self.profiles: dict[int, Profile] = {}  # fid -> its profile
        self._bands: dict[int, np.ndarray] = {}  # band index -> 2D array
        self._scale = 1.0  # plotted distance = meters (or px) / scale

        self.bandBox = QComboBox()
        for band in range(image.bandCount):
            self.bandBox.addItem(bandLabel(image, band), band)
        self.bandBox.currentIndexChanged.connect(lambda _: self._replot())
        self.plot = pg.PlotWidget()
        self.plotItem: pg.PlotItem = self.plot.getPlotItem()
        self.plotItem.showGrid(x=True, y=True, alpha=0.25)
        self.plotItem.addLegend(offset=(-10, 10))
        self.cursorLine = pg.InfiniteLine(angle=90, movable=False, pen=pg.mkPen("w"))
        self.cursorLine.setVisible(False)
        self.plotItem.addItem(self.cursorLine, ignoreBounds=True)
        scene = self.plot.scene()
        assert isinstance(scene, pg.GraphicsScene)
        scene.sigMouseMoved.connect(self._onMouseMoved)
        self.plot.getViewBox().sigRangeChanged.connect(
            lambda *_: self._showExaggeration()
        )
        self.readout = QLabel()
        self.exaggeration = MutedLabel("")
        self.exaggeration.setToolTip(
            "How much the vertical axis is stretched against the horizontal, "
            "for values in meters (a DEM)"
        )
        export = QPushButton("Export…")
        export.setToolTip("Save the profiles as CSV, or the plot as PNG, SVG or PDF")
        export.clicked.connect(self._export)
        top = QHBoxLayout()
        top.addWidget(QLabel("Band:"))
        top.addWidget(self.bandBox, 1)
        top.addWidget(export)
        bottom = QHBoxLayout()
        bottom.addWidget(self.readout, 1)
        bottom.addWidget(self.exaggeration)
        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.plot, 1)
        layout.addLayout(bottom)
        self.empty = MutedLabel("Draw a line with Draw Line to see its profile.")
        layout.addWidget(self.empty)
        self._replot()

    def band(self) -> int:
        return int(self.bandBox.currentData() or 0)

    def setLines(self, lines: Sequence[VardaLine]) -> None:
        self.lines = list(lines)
        self._replot()

    def _bandData(self, band: int) -> np.ndarray:
        if band not in self._bands:
            raw = self.image.getBands([band])
            data = np.ma.filled(raw, np.nan) if np.ma.isMaskedArray(raw) else raw
            data = np.asarray(data, dtype=float)[:, :, 0]
            nodata = self.image.nodata
            if nodata is not None and np.isfinite(nodata):
                data = np.where(data == nodata, np.nan, data)
            self._bands = {band: data}  # one band at a time: DEMs can be large
        return self._bands[band]

    def _replot(self) -> None:
        self.plotItem.clear()
        legend = self.plotItem.legend
        if legend is not None:
            legend.clear()
        self.plotItem.addItem(self.cursorLine, ignoreBounds=True)
        self.profiles = {}
        self.empty.setVisible(not self.lines)
        if not self.lines:
            self.readout.setText("")
            self.exaggeration.setText("")
            return
        band = self._bandData(self.band())
        georeferenced = self.image.hasGeospatialData
        for line in self.lines:
            self.profiles[line.fid] = profile(
                band,
                line.vertices,
                self.image.transform if georeferenced else None,
                self.image.crs if georeferenced else None,
            )
        units = next(iter(self.profiles.values())).distanceUnits
        longest = max(float(p.distance[-1]) for p in self.profiles.values())
        self._scale = 1000.0 if units == "m" and longest >= KM_FROM else 1.0
        unit = "km" if self._scale == 1000.0 else units
        for line in self.lines:
            result = self.profiles[line.fid]
            self.plot.plot(
                result.distance / self._scale,
                result.values,
                pen=pg.mkPen(line.color, width=2),
                name=line.name,
                connect="finite",
            )
        self.plot.setLabel("bottom", f"Distance ({unit})")
        self.plot.setLabel("left", self.bandBox.currentText())
        self.plot.enableAutoRange()
        self._showExaggeration()

    def _showExaggeration(self) -> None:
        if not self.profiles or self._unitsOf() != "m":
            self.exaggeration.setText("")
            return
        xPerPixel, yPerPixel = self.plot.getViewBox().viewPixelSize()
        if yPerPixel <= 0:
            return
        ratio = xPerPixel * self._scale / yPerPixel
        self.exaggeration.setText(f"Vertical exaggeration ≈ {ratio:.3g}×")

    def verticalExaggeration(self) -> float | None:
        if not self.profiles or self._unitsOf() != "m":
            return None
        xPerPixel, yPerPixel = self.plot.getViewBox().viewPixelSize()
        return xPerPixel * self._scale / yPerPixel if yPerPixel > 0 else None

    def _unitsOf(self) -> str:
        return next(iter(self.profiles.values())).distanceUnits if self.profiles else ""

    def _onMouseMoved(self, position) -> None:
        viewBox = self.plot.getViewBox()
        if not self.profiles or not viewBox.sceneBoundingRect().contains(position):
            self.cursorLine.setVisible(False)
            self.readout.setText("")
            self.sigCursor.emit(None)
            return
        distance = viewBox.mapSceneToView(position).x() * self._scale
        self.cursorLine.setPos(distance / self._scale)
        self.cursorLine.setVisible(True)
        parts, cursor = [], None
        for line in self.lines:
            result = self.profiles[line.fid]
            index = int(
                np.clip(
                    np.searchsorted(result.distance, distance),
                    0,
                    len(result.distance) - 1,
                )
            )
            value = result.values[index]
            if cursor is None:
                cursor = result.positions[index]
            text = "no data" if not np.isfinite(value) else f"{value:.4g}"
            parts.append(f"{line.name}: {text}")
        unit = "km" if self._scale == 1000.0 else self._unitsOf()
        self.readout.setText(
            f"{distance / self._scale:.4g} {unit}   " + "   ".join(parts)
        )
        self.sigCursor.emit(cursor)

    # --- export --------------------------------------------------------------

    def _export(self) -> None:
        if not self.profiles:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Profiles", "profiles.csv", EXPORT_FILTER
        )
        if not path:
            return
        try:
            self.exportTo(Path(path))
        except (OSError, ValueError) as error:
            QMessageBox.warning(self, "Export Profiles", str(error))

    def exportTo(self, path: Path) -> None:
        if path.suffix.lower() != ".csv":
            exportImage(self.plotItem, path)
            return
        georeferenced = self.image.hasGeospatialData
        units = self._unitsOf()
        with path.open("w", newline="") as f:
            out = csv.writer(f)
            header = ["line", f"distance_{units}", "x_px", "y_px"]
            if georeferenced:
                header += ["map_x", "map_y"]
            out.writerow([*header, self.bandBox.currentText()])
            for line in self.lines:
                result = self.profiles[line.fid]
                mapXY = (
                    self.image.imageToGeo(result.positions) if georeferenced else None
                )
                for i, (d, (x, y), v) in enumerate(
                    zip(result.distance, result.positions, result.values)
                ):
                    row = [line.name, f"{d:.6g}", f"{x:.3f}", f"{y:.3f}"]
                    if mapXY is not None:
                        row += [f"{mapXY[i, 0]:.6f}", f"{mapXY[i, 1]:.6f}"]
                    out.writerow([*row, "" if not np.isfinite(v) else f"{v:.10g}"])
