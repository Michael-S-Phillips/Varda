"""Export a spectral plot: publication-quality images (PNG, SVG, PDF) or the
plotted curves as CSV."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import pyqtgraph.exporters as exporters
from PyQt6.QtCore import QMarginsF, QRectF, QSizeF
from PyQt6.QtGui import QPageLayout, QPageSize, QPainter, QPdfWriter
from PyQt6.QtSvg import QSvgGenerator

from varda.common.spectral_axis import SpectralUnit

if TYPE_CHECKING:
    from varda.plotting.plot import VardaPlotWidget

EXPORT_FILTER = (
    "PNG image (*.png);;SVG vector image (*.svg);;PDF (*.pdf);;CSV data (*.csv)"
)
MIN_PNG_WIDTH = 2000  # px; about 300 dpi across a journal column and a half
PDF_DPI = 300
_UNIT_COLUMN = {
    SpectralUnit.NANOMETRE: "wavelength_nm",
    SpectralUnit.MICROMETRE: "wavelength_um",
    SpectralUnit.WAVENUMBER: "wavenumber_cm-1",
}


def exportPlot(widget: VardaPlotWidget, path: str | Path) -> Path:
    """Write the plot to ``path``; the suffix picks the format."""
    target = Path(path)
    writers = {".png": _png, ".svg": _svg, ".pdf": _pdf, ".csv": _csv}
    writer = writers.get(target.suffix.lower())
    if writer is None:
        raise ValueError(f"Cannot export '{target.suffix}'; use png, svg, pdf or csv.")
    writer(widget, target)
    return target


def _png(widget: VardaPlotWidget, target: Path) -> None:
    exporter = exporters.ImageExporter(widget.plotItem)
    width = max(MIN_PNG_WIDTH, int(widget.plotItem.sceneBoundingRect().width() * 3))
    exporter.parameters()["width"] = width
    exporter.export(str(target))


def _svg(widget: VardaPlotWidget, target: Path) -> None:
    # Qt's own SVG writer: pyqtgraph's SVGExporter calls paint() on PlotDataItem
    # containers, which raises under PyQt6
    source = widget.plotItem.sceneBoundingRect()
    generator = QSvgGenerator()
    generator.setFileName(str(target))
    generator.setSize(source.size().toSize())
    generator.setViewBox(QRectF(0, 0, source.width(), source.height()))
    generator.setTitle("Varda spectra")
    _render(widget, generator, QRectF(0, 0, source.width(), source.height()))


def _render(widget: VardaPlotWidget, device, targetRect: QRectF) -> None:
    painter = QPainter(device)
    try:
        scene = widget.plotItem.scene()
        if scene is not None:
            scene.render(painter, targetRect, widget.plotItem.sceneBoundingRect())
    finally:
        painter.end()


def _pdf(widget: VardaPlotWidget, target: Path) -> None:
    source = widget.plotItem.sceneBoundingRect()
    writer = QPdfWriter(str(target))
    writer.setResolution(PDF_DPI)
    # A page the shape of the plot, 6 inches wide
    widthInches = 6.0
    heightInches = widthInches * source.height() / max(source.width(), 1.0)
    pageSize = QPageSize(QSizeF(widthInches, heightInches), QPageSize.Unit.Inch)
    writer.setPageLayout(
        QPageLayout(pageSize, QPageLayout.Orientation.Portrait, QMarginsF())
    )
    _render(widget, writer, QRectF(0, 0, writer.width(), writer.height()))


def _csv(widget: VardaPlotWidget, target: Path) -> None:
    curves = [
        (c.plotDataItem.name() or f"curve {i + 1}", *c.displayedData())
        for i, c in enumerate(widget.plots)
    ]
    xColumn = _UNIT_COLUMN.get(widget.spectralUnit, "x") if widget.spectralUnit else "x"
    with target.open("w", newline="") as f:
        out = csv.writer(f)
        sharedX = bool(curves) and all(
            len(x) == len(curves[0][1]) and np.allclose(x, curves[0][1], equal_nan=True)
            for _, x, _ in curves
        )
        if sharedX:
            out.writerow([xColumn, *[name for name, _, _ in curves]])
            for row in zip(curves[0][1], *[y for _, _, y in curves]):
                out.writerow([f"{v:.10g}" for v in row])
        else:
            out.writerow(["curve", "x", "y"])
            for name, x, y in curves:
                for xv, yv in zip(x, y):
                    out.writerow([name, f"{xv:.10g}", f"{yv:.10g}"])
