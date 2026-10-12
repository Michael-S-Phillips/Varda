"""The n-D visualizer: candidate pure pixels in MNF space, projected to 2-D.

A grand tour rotates the projection smoothly through the chosen MNF
dimensions so corners of the data cloud (the endmembers) come into view.
Drag a lasso around a corner to put those pixels in the active endmember;
Shift-drag takes them out. "Collapse classes" projects out the directions of
the classes already found, so the next corner stands out.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pyqtgraph as pg
from matplotlib.path import Path
from PyQt6.QtCore import QPointF, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from varda.analysis.endmembers import interpolatePlane, randomPlane

_FRAME_MS = 33
_HOVER_PIXELS = 7.0


class _LassoViewBox(pg.ViewBox):
    """Left-drag draws a lasso; right/middle drag and the wheel pan and zoom."""

    sigLassoFinished = pyqtSignal(object, bool)  # [(x, y), ...] view coords, add

    def __init__(self) -> None:
        super().__init__(lockAspect=True)
        self._path: list[QPointF] = []
        self._curve = pg.PlotCurveItem(pen=pg.mkPen("#ffff00", width=1.5))
        self.addItem(self._curve, ignoreBounds=True)
        self.setMouseMode(pg.ViewBox.PanMode)

    def mouseDragEvent(self, ev, axis=None):
        if ev.button() != Qt.MouseButton.LeftButton:
            super().mouseDragEvent(ev, axis)
            return
        ev.accept()
        point = self.mapSceneToView(ev.scenePos())
        if ev.isStart():
            self._path = [point]
        else:
            self._path.append(point)
        xs = [p.x() for p in self._path] + [self._path[0].x()]
        ys = [p.y() for p in self._path] + [self._path[0].y()]
        self._curve.setData(xs, ys)
        if ev.isFinish():
            polygon = [(p.x(), p.y()) for p in self._path]
            remove = bool(ev.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            self._curve.setData([], [])
            self._path = []
            if len(polygon) >= 3:
                self.sigLassoFinished.emit(polygon, not remove)


class NdVisualizer(QWidget):
    UNASSIGNED_COLOR = "#d0d0d0"
    BACKGROUND_COLOR = (90, 90, 90, 90)

    sigLassoSelected = pyqtSignal(object, bool)  # pixel ids (ndarray), add
    sigPointHovered = pyqtSignal(object)  # pixel id or None

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._rng = np.random.default_rng()
        self._data = np.zeros((0, 2))
        self._background = np.zeros((0, 2))
        self._ids = np.zeros(0, dtype=np.int64)
        self._colors: list[str] = []
        self._dims: list[int] = []
        self._collapse: np.ndarray | None = None  # projector removing class directions
        self._plane = np.eye(2)
        self._start = np.eye(2)
        self._target = np.eye(2)
        self._t = 0.0
        self._projected = np.zeros((0, 2))
        self._hovered: int | None = None

        self.viewBox = _LassoViewBox()
        self.viewBox.sigLassoFinished.connect(self.selectPolygon)
        self.plotWidget = pg.PlotWidget(viewBox=self.viewBox)
        self.plotWidget.hideAxis("left")
        self.plotWidget.hideAxis("bottom")
        self.plotWidget.setMenuEnabled(False)
        self.backgroundItem = pg.ScatterPlotItem(
            size=2, pen=None, brush=pg.mkBrush(*self.BACKGROUND_COLOR)
        )
        self.scatter = pg.ScatterPlotItem(size=5, pen=None)
        self.hoverItem = pg.ScatterPlotItem(
            size=12, pen=pg.mkPen("#ffffff", width=2), brush=None
        )
        for item in (self.backgroundItem, self.scatter, self.hoverItem):
            self.viewBox.addItem(item)
        scene = self.plotWidget.scene()
        assert isinstance(scene, pg.GraphicsScene)
        scene.sigMouseMoved.connect(self._onMouseMoved)

        self._timer = QTimer(self)
        self._timer.setInterval(_FRAME_MS)
        self._timer.timeout.connect(self.step)

        self.playButton = QPushButton("▶ Play")
        self.playButton.setCheckable(True)
        self.playButton.toggled.connect(self._onPlayToggled)
        stepButton = QPushButton("Step")
        stepButton.clicked.connect(self.step)
        newButton = QPushButton("New View")
        newButton.setToolTip("Jump to a new random projection")
        newButton.clicked.connect(self.newProjection)
        self.speedSlider = QSlider(Qt.Orientation.Horizontal)
        self.speedSlider.setRange(1, 20)
        self.speedSlider.setValue(5)
        self.speedSlider.setMaximumWidth(120)
        self.speedSlider.setToolTip("Tour speed")
        self.collapseBox = QCheckBox("Collapse classes")
        self.collapseBox.setToolTip(
            "Project out the directions of the classes found so far, so the "
            "next corner of the cloud stands out"
        )
        self.backgroundBox = QCheckBox("All pixels")
        self.backgroundBox.setChecked(True)
        self.backgroundBox.setToolTip(
            "Show a sample of every pixel faintly, for context"
        )
        self.backgroundBox.toggled.connect(self.backgroundItem.setVisible)
        self.sizeSlider = QSlider(Qt.Orientation.Horizontal)
        self.sizeSlider.setRange(2, 14)
        self.sizeSlider.setValue(5)
        self.sizeSlider.setMaximumWidth(80)
        self.sizeSlider.setToolTip("Point size")
        self.sizeSlider.valueChanged.connect(self.scatter.setSize)

        self._dimButtons: list[QToolButton] = []
        self.dimsLayout = QHBoxLayout()
        self.dimsLayout.setSpacing(2)
        self.hintLabel = QLabel()
        self.hintLabel.setWordWrap(True)

        controls = QHBoxLayout()
        for widget in (
            self.playButton,
            stepButton,
            newButton,
            QLabel("Speed"),
            self.speedSlider,
        ):
            controls.addWidget(widget)
        controls.addStretch()
        controls.addWidget(self.collapseBox)
        controls.addWidget(self.backgroundBox)
        controls.addWidget(QLabel("Size"))
        controls.addWidget(self.sizeSlider)
        dims = QHBoxLayout()
        dims.addWidget(QLabel("MNF dimensions:"))
        dims.addLayout(self.dimsLayout)
        dims.addStretch()

        layout = QVBoxLayout(self)
        layout.addLayout(controls)
        layout.addLayout(dims)
        layout.addWidget(self.plotWidget, stretch=1)
        layout.addWidget(self.hintLabel)

    # --- data -----------------------------------------------------------------------

    def setData(
        self,
        points: np.ndarray,
        pixelIds: np.ndarray,
        *,
        background: np.ndarray | None = None,
    ) -> None:
        """``points`` (n, k) in MNF space, one row per candidate pixel id."""
        points = np.asarray(points, dtype=np.float64)
        k = points.shape[1] if points.ndim == 2 else 0
        centre = points.mean(axis=0) if points.size else np.zeros(k)
        self._data = points - centre
        self._ids = np.asarray(pixelIds, dtype=np.int64)
        self._background = (
            np.zeros((0, k)) if background is None else np.asarray(background) - centre
        )
        self._colors = [self.UNASSIGNED_COLOR] * self._ids.size
        previous = set(self._dims)
        self._rebuildDimButtons(k)
        dims = [d for d in range(k) if d in previous] if previous else list(range(k))
        self.setActiveDims(dims if len(dims) >= 2 else list(range(k)))

    def _rebuildDimButtons(self, k: int) -> None:
        for button in self._dimButtons:
            self.dimsLayout.removeWidget(button)
            button.deleteLater()
        self._dimButtons = []
        for d in range(k):
            button = QToolButton()
            button.setText(str(d + 1))
            button.setCheckable(True)
            button.setToolTip(f"Include MNF {d + 1} in the tour")
            button.toggled.connect(self._onDimToggled)
            self.dimsLayout.addWidget(button)
            self._dimButtons.append(button)

    def _onDimToggled(self) -> None:
        dims = [d for d, b in enumerate(self._dimButtons) if b.isChecked()]
        if len(dims) >= 2:
            self.setActiveDims(dims)
        else:  # keep at least two: undo the click
            self._syncDimButtons()

    def _syncDimButtons(self) -> None:
        for d, button in enumerate(self._dimButtons):
            button.blockSignals(True)
            button.setChecked(d in self._dims)
            button.blockSignals(False)

    def activeDims(self) -> list[int]:
        return list(self._dims)

    def setActiveDims(self, dims: Sequence[int]) -> None:
        k = self._data.shape[1]
        self._dims = sorted(int(d) for d in dims if 0 <= d < k)
        self._syncDimButtons()
        self._plane = self._randomPlane()
        self._start = self._plane
        self._target = self._randomPlane()
        self._t = 0.0
        self._fitView()
        self._redraw()

    def setPointColors(self, colors: dict[int, str]) -> None:
        """Colour per pixel id (pixels not listed are unassigned)."""
        self._colors = [colors.get(int(i), self.UNASSIGNED_COLOR) for i in self._ids]
        self._redraw()

    def pointColors(self) -> list[str]:
        return list(self._colors)

    def setCollapseMeans(self, means: Sequence[np.ndarray] | None) -> None:
        """Project out the span of the differences between ``means`` (class
        means in the same coordinates as the data), or stop collapsing."""
        if means is None or len(means) < 2:
            self._collapse = None
        else:
            M = np.asarray(means, dtype=np.float64)
            differences = (M[1:] - M[0]).T  # (k, classes - 1)
            q, r = np.linalg.qr(differences)
            q = q[:, np.abs(np.diag(r)) > 1e-12]
            self._collapse = np.eye(M.shape[1]) - q @ q.T
        self._redraw()

    def setHint(self, text: str) -> None:
        self.hintLabel.setText(text)

    # --- projection -------------------------------------------------------------------

    def _randomPlane(self) -> np.ndarray:
        k = self._data.shape[1]
        plane = np.zeros((k, 2))
        if len(self._dims) >= 2:
            plane[self._dims] = randomPlane(len(self._dims), self._rng)
        return plane

    def plane(self) -> np.ndarray:
        return self._plane

    def projectPoints(self, points: np.ndarray) -> np.ndarray:
        """Project points given in the data's centred coordinates."""
        data = np.asarray(points, dtype=np.float64)
        if self._collapse is not None:
            data = data @ self._collapse
        return data @ self._plane

    def projected(self) -> np.ndarray:
        return self._projected

    def step(self) -> None:
        """Advance the tour one frame towards the next random view."""
        if self._data.shape[1] < 2:
            return
        self._t += 0.004 * self.speedSlider.value()
        if self._t >= 1.0:
            self._start, self._target, self._t = self._target, self._randomPlane(), 0.0
        self._plane = interpolatePlane(self._start, self._target, self._t)
        self._redraw()

    def newProjection(self) -> None:
        self._plane = self._randomPlane()
        self._start, self._target, self._t = self._plane, self._randomPlane(), 0.0
        self._redraw()

    def _fitView(self) -> None:
        if not self._data.size or not self._dims:
            return
        radius = float(np.max(np.linalg.norm(self._data[:, self._dims], axis=1))) * 1.05
        radius = radius or 1.0
        self.viewBox.setRange(
            xRange=(-radius, radius), yRange=(-radius, radius), padding=0
        )

    def _redraw(self) -> None:
        if self._data.shape[1] < 2:
            self.scatter.setData([], [])
            return
        self._projected = self.projectPoints(self._data)
        brushes = [pg.mkBrush(c) for c in self._colors]
        self.scatter.setData(
            pos=self._projected,
            brush=brushes,
            data=self._ids,
            size=self.sizeSlider.value(),
        )
        if self._background.size:
            bg = self.projectPoints(self._background)
            self.backgroundItem.setData(pos=bg)
        self._updateHoverMarker()

    def _onPlayToggled(self, playing: bool) -> None:
        self.playButton.setText("⏸ Pause" if playing else "▶ Play")
        if playing:
            self._timer.start()
        else:
            self._timer.stop()

    # --- interaction --------------------------------------------------------------------

    def selectPolygon(self, polygon: Sequence[tuple[float, float]], add: bool) -> None:
        if not self._projected.size:
            return
        inside = Path(np.asarray(polygon, dtype=np.float64)).contains_points(
            self._projected
        )
        self.sigLassoSelected.emit(self._ids[inside], add)

    def pointNear(self, x: float, y: float) -> int | None:
        """Pixel id of the projected point within a few screen pixels of (x, y)."""
        if not self._projected.size:
            return None
        pixel = self.viewBox.viewPixelSize()
        scale = np.array([pixel[0] or 1.0, pixel[1] or 1.0])
        distances = np.linalg.norm((self._projected - (x, y)) / scale, axis=1)
        nearest = int(np.argmin(distances))
        if distances[nearest] > _HOVER_PIXELS:
            return None
        return int(self._ids[nearest])

    def _onMouseMoved(self, scenePos) -> None:
        if not self.viewBox.sceneBoundingRect().contains(scenePos):
            return
        point = self.viewBox.mapSceneToView(scenePos)
        hovered = self.pointNear(point.x(), point.y())
        if hovered != self._hovered:
            self._hovered = hovered
            self._updateHoverMarker()
            self.sigPointHovered.emit(hovered)

    def highlightPixel(self, pixelId: int | None) -> None:
        """Ring a pixel's point (e.g. one hovered in the image)."""
        self._hovered = pixelId
        self._updateHoverMarker()

    def _updateHoverMarker(self) -> None:
        if self._hovered is None:
            self.hoverItem.setData([], [])
            return
        where = np.flatnonzero(self._ids == self._hovered)
        if where.size:
            self.hoverItem.setData(pos=self._projected[where])
        else:
            self.hoverItem.setData([], [])
