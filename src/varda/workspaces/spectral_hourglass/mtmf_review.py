"""Review an MTMF result: matched-filter score against infeasibility for one
endmember, with draggable thresholds that pick the detections live.

True detections have a high score and low infeasibility; a high score with
high infeasibility is a false alarm (Boardman 1998).
"""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource

_MAX_POINTS = 30_000


class MtmfReview(QWidget):
    sigDetectionsChanged = pyqtSignal(object, str)  # (rows, cols) bool mask, color
    sigAddToProject = pyqtSignal(object)  # VardaRaster

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._result: VardaRaster | None = None
        self._score = np.zeros((0, 0))
        self._infeasibility = np.zeros((0, 0))

        self.endmemberBox = QComboBox()
        self.endmemberBox.currentIndexChanged.connect(lambda _: self._showEndmember())
        self.plot = pg.PlotWidget()
        self.plot.setMinimumHeight(200)
        self.plot.setLabel("bottom", "MF score")
        self.plot.setLabel("left", "Infeasibility")
        self.scatter = pg.ScatterPlotItem(
            size=3, pen=None, brush=pg.mkBrush(200, 200, 200, 90)
        )
        self.selected = pg.ScatterPlotItem(size=4, pen=None)
        self.plot.addItem(self.scatter)
        self.plot.addItem(self.selected)
        self.scoreLine = pg.InfiniteLine(
            pos=0.5,
            angle=90,
            movable=True,
            pen=pg.mkPen("#ffff00", width=2),
            label="MF ≥ {value:.2f}",
            labelOpts={"position": 0.95, "color": "#ffff00"},
        )
        self.infeasibilityLine = pg.InfiniteLine(
            pos=5.0,
            angle=0,
            movable=True,
            pen=pg.mkPen("#00ffff", width=2),
            label="infeasibility ≤ {value:.1f}",
            labelOpts={"position": 0.8, "color": "#00ffff"},
        )
        for line in (self.scoreLine, self.infeasibilityLine):
            self.plot.getPlotItem().addItem(line, ignoreBounds=True)
            line.sigPositionChanged.connect(lambda _: self._update())
        self.summary = QLabel()
        addButton = QPushButton("Add Detections to Project")
        addButton.clicked.connect(
            lambda: self.sigAddToProject.emit(self.detectionsRaster())
        )

        top = QHBoxLayout()
        top.addWidget(QLabel("Endmember"))
        top.addWidget(self.endmemberBox, stretch=1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(top)
        layout.addWidget(self.plot, stretch=1)
        layout.addWidget(self.summary)
        layout.addWidget(addButton)

    def setResult(self, result: VardaRaster) -> None:
        self._result = result
        names = list(result.extraMetadata.get("classes", []))
        self.endmemberBox.blockSignals(True)
        self.endmemberBox.clear()
        self.endmemberBox.addItems(names)
        self.endmemberBox.blockSignals(False)
        # loading a result does not announce detections: only the user's
        # thresholds (or endmember choice) do, so the map overlay stays up
        self.blockSignals(True)
        try:
            self._showEndmember()
        finally:
            self.blockSignals(False)

    def _bands(self) -> tuple[np.ndarray, np.ndarray]:
        assert self._result is not None
        name = self.endmemberBox.currentText()
        bandNames = list(self._result.bandNames)
        data = self._result.getData()
        score = data[:, :, bandNames.index(f"MF({name})")]
        infeasibility = data[:, :, bandNames.index(f"Infeasibility({name})")]
        return score, infeasibility

    def _color(self) -> str:
        assert self._result is not None
        colors = self._result.extraMetadata.get("classColors", [])
        index = self.endmemberBox.currentIndex()
        return colors[index] if 0 <= index < len(colors) else "#ffff00"

    def _showEndmember(self) -> None:
        if self._result is None or self.endmemberBox.currentIndex() < 0:
            return
        self._score, self._infeasibility = self._bands()
        finite = np.isfinite(self._score) & np.isfinite(self._infeasibility)
        x, y = self._score[finite], self._infeasibility[finite]
        if x.size > _MAX_POINTS:
            pick = np.random.default_rng(0).choice(x.size, _MAX_POINTS, replace=False)
            x, y = x[pick], y[pick]
        self.scatter.setData(x, y)
        self.selected.setBrush(pg.mkBrush(self._color()))
        self._update()

    def setThresholds(self, *, minScore: float, maxInfeasibility: float) -> None:
        self.scoreLine.blockSignals(True)
        self.scoreLine.setValue(minScore)
        self.scoreLine.blockSignals(False)
        self.infeasibilityLine.setValue(maxInfeasibility)
        self._update()

    def detections(self) -> np.ndarray:
        with np.errstate(invalid="ignore"):
            return (self._score >= self.scoreLine.value()) & (
                self._infeasibility <= self.infeasibilityLine.value()
            )

    def _update(self) -> None:
        if self._result is None or self._score.size == 0:
            return
        mask = self.detections()
        self.selected.setData(self._score[mask], self._infeasibility[mask])
        self.summary.setText(
            f"{int(mask.sum()):,} pixels with MF ≥ {self.scoreLine.value():.2f} "
            f"and infeasibility ≤ {self.infeasibilityLine.value():.1f}"
        )
        self.sigDetectionsChanged.emit(mask, self._color())

    def detectionsRaster(self) -> VardaRaster:
        assert self._result is not None
        result = self._result
        name = self.endmemberBox.currentText()
        values = np.where(self.detections(), self._score, np.nan).astype(np.float32)
        band = f"MF({name}) detections"
        source = ArrayDataSource(
            values[:, :, np.newaxis],
            wavelengths=np.array([band]),
            bandNames=[band],
            transform=result.transform,
            crs=result.crs,
            description=(
                f"MTMF detections of {name}: MF ≥ {self.scoreLine.value():.2f}, "
                f"infeasibility ≤ {self.infeasibilityLine.value():.1f}"
            ),
        )
        base = result.name.removesuffix(" MTMF")
        return VardaRaster(source, name=f"{base} MTMF detections {name}")
