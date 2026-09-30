"""Scree plot of a transform's eigenvalues with a draggable "keep N" cutoff."""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg

from varda.common.parameter import IntParameter


class EigenvaluePlot(pg.PlotWidget):
    """Eigenvalue against component number. The vertical cutoff line and the
    ``components`` parameter follow each other, so the user can drag the line
    to where the eigenvalues flatten into noise."""

    def __init__(
        self,
        eigenvalues,
        components: IntParameter,
        *,
        logScale: bool = True,
        parent=None,
    ) -> None:
        super().__init__(parent)
        values = np.asarray(eigenvalues, dtype=np.float64)
        count = values.size
        self._components = components

        self.setMinimumHeight(180)
        self.setLabel("bottom", "Component")
        self.setLabel("left", "Eigenvalue")
        self.setMouseEnabled(x=False, y=False)
        self.setMenuEnabled(False)
        if logScale:
            positive = values[values > 0]
            floor = positive.min() * 0.1 if positive.size else 1e-12
            values = np.maximum(values, floor)
        self.setLogMode(x=False, y=logScale)
        self.plot(
            np.arange(1, count + 1),
            values,
            pen=pg.mkPen("#cccccc"),
            symbol="o",
            symbolSize=5,
            symbolBrush="#ffffff",
        )

        self.cutoff = pg.InfiniteLine(
            pos=components.get(),
            angle=90,
            movable=True,
            bounds=(1, max(count, 1)),
            pen=pg.mkPen("#ffff00", width=2),
            hoverPen=pg.mkPen("#ffff00", width=3),
            label="keep {value:.0f}",
            labelOpts={"position": 0.9, "color": "#ffff00", "fill": "#00000080"},
        )
        self.getPlotItem().addItem(self.cutoff, ignoreBounds=True)
        self.cutoff.sigPositionChanged.connect(self._onCutoffMoved)
        components.sigParameterChanged.connect(self._onComponentsChanged)

    def _onCutoffMoved(self) -> None:
        count = int(round(self.cutoff.value()))
        if count != self._components.get():
            self._components.set(count)

    def _onComponentsChanged(self, value: int) -> None:
        if self.cutoff.value() != value:
            self.cutoff.setValue(int(value))
