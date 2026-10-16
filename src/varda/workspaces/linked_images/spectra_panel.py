"""Linked spectra: one plot per image, stacked, each showing that image's
spectrum where the linked cursor is. Products of one pipeline (a result,
its sample counts, its flags) have different units, so each gets its own
vertical axis; images with the same spectral axis share the horizontal one."""

from __future__ import annotations

import csv
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from varda.common.entities import VardaRaster
from varda.common.palette import classColor
from varda.common.ui import MutedLabel
from varda.workspaces.linked_images.linking import LinkedSpectrum, spectrumAt


class LinkedSpectraPanel(QWidget):
    def __init__(self, images: Sequence[VardaRaster], parent: QWidget | None = None):
        super().__init__(parent)
        self.images = list(images)
        self.spectra: list[LinkedSpectrum | None] = [None] * len(self.images)
        self.layoutWidget = pg.GraphicsView()
        stack = pg.GraphicsLayout()
        self.layoutWidget.setCentralItem(stack)
        self.plots: list[pg.PlotItem] = []
        self.curves: list[pg.PlotDataItem] = []
        for row, image in enumerate(self.images):
            plot = pg.PlotItem()
            stack.addItem(plot, row=row, col=0)
            plot.setTitle(image.name, size="9pt")
            plot.showGrid(x=True, y=True, alpha=0.2)
            curve = plot.plot(pen=pg.mkPen(classColor(row), width=1.5))
            self.plots.append(plot)
            self.curves.append(curve)
        self.hint = MutedLabel(
            "Ctrl+click or Ctrl+drag in any view to read every image there."
        )
        self.hint.setWordWrap(True)
        export = QPushButton("Export…")
        export.setToolTip("Save the spectra at the cursor as CSV")
        export.clicked.connect(self._export)
        bottom = QHBoxLayout()
        bottom.addWidget(self.hint, 1)
        bottom.addWidget(export)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.layoutWidget, 1)
        layout.addLayout(bottom)

    def showAt(self, positions: Sequence[np.ndarray]) -> None:
        """Each image's spectrum at its position (image coordinates)."""
        axes: dict[str, pg.PlotItem] = {}
        for i, (image, point) in enumerate(zip(self.images, positions)):
            x, y = (float(v) for v in np.asarray(point).reshape(-1)[:2])
            spectrum = spectrumAt(image, x, y)
            self.spectra[i] = spectrum
            plot, curve = self.plots[i], self.curves[i]
            if spectrum is None:
                curve.setData([], [])
                plot.setTitle(f"{image.name}: off the image", size="9pt")
                continue
            curve.setData(spectrum.displayAxis, spectrum.values, connect="finite")
            plot.setTitle(f"{image.name} ({int(x)}, {int(y)})", size="9pt")
            plot.setLabel("bottom", spectrum.axisLabel)
            # plots on the same spectral axis pan and zoom together
            first = axes.setdefault(spectrum.axisLabel, plot)
            plot.getViewBox().setXLink(
                first.getViewBox() if first is not plot else None
            )

    def _export(self) -> None:
        if not any(s is not None for s in self.spectra):
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Spectra", "linked_spectra.csv", "CSV data (*.csv)"
        )
        if path:
            try:
                self.exportTo(Path(path))
            except OSError as error:
                QMessageBox.warning(self, "Export Spectra", str(error))

    def exportTo(self, path: Path) -> None:
        with path.open("w", newline="") as f:
            out = csv.writer(f)
            out.writerow(["image", "x", "value"])
            for image, spectrum in zip(self.images, self.spectra):
                if spectrum is None:
                    continue
                for x, value in zip(spectrum.displayAxis, spectrum.values):
                    out.writerow(
                        [
                            image.name,
                            f"{x:.6g}",
                            "" if np.isnan(value) else f"{value:.10g}",
                        ]
                    )
