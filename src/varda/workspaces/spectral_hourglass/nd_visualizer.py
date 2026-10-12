"""The n-D visualizer: candidate pure pixels in MNF space, projected to 2-D.

A grand tour rotates the projection smoothly through the chosen MNF
dimensions so corners of the data cloud (the endmembers) come into view; in
Rotate mode dragging turns the cloud by hand. In Lasso mode, drag around a
corner to put those pixels in the active endmember (Shift-drag takes them
out). Axis arrows show how each MNF dimension lies in the current view.
"Collapse classes" projects out the directions of the classes already found,
so the next corner stands out.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pyqtgraph as pg
from matplotlib.path import Path
from PyQt6.QtCore import QPointF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QBrush, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QButtonGroup,
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
_FIT_PLANES = 12  # random projections sampled to size the view
_STEP_REPEAT_MS = 33  # holding Step advances the tour at the Play frame rate
_ROTATE_RADIANS_PER_PIXEL = 0.008  # a drag across the view turns ~half a turn


class _CloudViewBox(pg.ViewBox):
    """Left-drag lassoes or rotates (by mode); right- or middle-drag pans; the
    wheel zooms."""

    sigLassoFinished = pyqtSignal(object, bool)  # [(x, y), ...] view coords, add
    sigRotateStart = pyqtSignal()
    sigRotateDrag = pyqtSignal(float, float)  # screen pixels from the press (dx, dy)
    sigRotateEnd = pyqtSignal()

    def __init__(self) -> None:
        super().__init__(lockAspect=True)
        self.lassoMode = False
        self._path: list[QPointF] = []
        self._curve = pg.PlotCurveItem(pen=pg.mkPen("#ffff00", width=1.5))
        self.addItem(self._curve, ignoreBounds=True)
        self.setMouseMode(pg.ViewBox.PanMode)

    def mouseDragEvent(self, ev, axis=None):
        ev.accept()
        if ev.button() != Qt.MouseButton.LeftButton:
            # pan (pyqtgraph's own right-drag would zoom)
            delta = self.mapToView(ev.pos()) - self.mapToView(ev.lastPos())
            self.translateBy(x=-delta.x(), y=-delta.y())
            return
        if not self.lassoMode:
            if ev.isStart():
                self.sigRotateStart.emit()
            d = ev.pos() - ev.buttonDownPos()
            self.sigRotateDrag.emit(float(d.x()), float(d.y()))
            if ev.isFinish():
                self.sigRotateEnd.emit()
            return
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
    AXIS_COLOR = "#7fb3d5"
    ROTATE = "rotate"
    LASSO = "lasso"

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

        self.viewBox = _CloudViewBox()
        self.viewBox.sigLassoFinished.connect(self.selectPolygon)
        self.viewBox.sigRotateStart.connect(self.beginRotate)
        self.viewBox.sigRotateDrag.connect(self.dragRotate)
        self.viewBox.sigRotateEnd.connect(self.endRotate)
        self._rotateFrame: np.ndarray | None = None  # [u, v, depth] frozen at the press
        self._resumeTour = False
        self._brushes: list[QBrush] = []
        self._axisItems: list[pg.GraphicsObject] = []
        self._radius = 1.0
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
        self.stepButton = QPushButton("Step")
        self.stepButton.setToolTip("Click to advance one frame; hold to keep turning")
        self.stepButton.setAutoRepeat(True)
        self.stepButton.setAutoRepeatDelay(250)
        self.stepButton.setAutoRepeatInterval(_STEP_REPEAT_MS)
        self.stepButton.clicked.connect(self.step)
        self.rotateButton = QToolButton()
        self.rotateButton.setText("Rotate")
        self.rotateButton.setToolTip("Drag to turn the cloud (R)")
        self.lassoButton = QToolButton()
        self.lassoButton.setText("Lasso")
        self.lassoButton.setToolTip(
            "Drag around points to add them to the active endmember; Shift-drag "
            "removes (L)"
        )
        self._modeGroup = QButtonGroup(self)
        for button in (self.rotateButton, self.lassoButton):
            button.setCheckable(True)
            self._modeGroup.addButton(button)
        self.rotateButton.clicked.connect(lambda: self.setMode(self.ROTATE))
        self.lassoButton.clicked.connect(lambda: self.setMode(self.LASSO))
        for key, mode in (("R", self.ROTATE), ("L", self.LASSO)):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(lambda m=mode: self.setMode(m))
        self.axesBox = QCheckBox("Axes")
        self.axesBox.setChecked(True)
        self.axesBox.setToolTip(
            "Arrows show how each MNF dimension in the tour lies in the current view: "
            "a long arrow means that dimension spreads the cloud along it"
        )
        self.axesBox.toggled.connect(lambda _: self._drawAxes())
        newButton = QPushButton("New View")
        newButton.setToolTip("Jump to a new random projection")
        newButton.clicked.connect(self.newProjection)
        self.speedSlider = QSlider(Qt.Orientation.Horizontal)
        self.speedSlider.setRange(1, 20)
        self.speedSlider.setValue(5)
        self.speedSlider.setMinimumWidth(70)
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
        self.sizeSlider.setMinimumWidth(50)
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
            self.rotateButton,
            self.lassoButton,
            self.playButton,
            self.stepButton,
            newButton,
            QLabel("Speed"),
            self.speedSlider,
        ):
            controls.addWidget(widget)
        controls.addStretch()
        dims = QHBoxLayout()
        dimsLabel = QLabel("Tour through MNF:")
        dimsLabel.setToolTip(
            "The cloud is rotated through these MNF components. Untick one to hold "
            "it out of every view, e.g. a noisy component or one you have explored."
        )
        dims.addWidget(dimsLabel)
        dims.addLayout(self.dimsLayout)
        dims.addStretch()
        dims.addWidget(self.collapseBox)
        dims.addWidget(self.axesBox)
        dims.addWidget(self.backgroundBox)
        dims.addWidget(QLabel("Size"))
        dims.addWidget(self.sizeSlider)

        layout = QVBoxLayout(self)
        layout.addLayout(controls)
        layout.addLayout(dims)
        layout.addWidget(self.plotWidget, stretch=1)
        layout.addWidget(self.hintLabel)
        self.setMode(self.ROTATE)

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
        self._brushes = []
        previous = set(self._dims)
        self._rebuildDimButtons(k)
        dims = [d for d in range(k) if d in previous] if previous else list(range(k))
        self.setActiveDims(dims if len(dims) >= 2 else list(range(k)))

    def _rebuildDimButtons(self, k: int) -> None:
        if len(self._dimButtons) == k:
            return
        for button in self._dimButtons:
            self.dimsLayout.removeWidget(button)
            button.setParent(None)
            button.deleteLater()
        self._dimButtons = []
        for d in range(k):
            button = QToolButton()
            button.setText(str(d + 1))
            button.setCheckable(True)
            button.setToolTip(
                f"Include MNF {d + 1} in the tour (its arrow shows how it lies in the view)"
            )
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
        self._brushes = []
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

    # --- modes -----------------------------------------------------------------------

    def mode(self) -> str:
        return self.LASSO if self.viewBox.lassoMode else self.ROTATE

    def setMode(self, mode: str) -> None:
        lasso = mode == self.LASSO
        self.viewBox.lassoMode = lasso
        self.lassoButton.setChecked(lasso)
        self.rotateButton.setChecked(not lasso)
        self._setCursor(
            Qt.CursorShape.CrossCursor if lasso else Qt.CursorShape.OpenHandCursor
        )

    def _setCursor(self, shape: Qt.CursorShape) -> None:
        viewport = self.plotWidget.viewport()
        if viewport is not None:
            viewport.setCursor(shape)

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
            # carry on from where the view actually is (the same plane as the
            # target, but its basis may be turned within it): no snap
            self._start = interpolatePlane(self._start, self._target, 1.0)
            self._target, self._t = self._randomPlane(), self._t - 1.0
        self._plane = interpolatePlane(self._start, self._target, self._t)
        self._redraw()

    def beginRotate(self) -> None:
        """Freeze the view's frame (x axis, y axis, and the hidden direction the
        cloud spreads along most) for a trackball drag; pause the tour."""
        hidden = self._hiddenDirection()
        if hidden is None:
            self._rotateFrame = None
            return
        self._rotateFrame = np.column_stack([self._plane, hidden])
        self._resumeTour = self._timer.isActive()
        self._timer.stop()
        self._setCursor(Qt.CursorShape.ClosedHandCursor)

    def dragRotate(self, dx: float, dy: float) -> None:
        """Turn the cloud like a trackball by the drag (dx, dy) in screen
        pixels from the press: points follow the cursor, and the turn depends
        only on the offset, so dragging back undoes it."""
        if self._rotateFrame is None:
            return
        up = -dy  # screen y grows downwards, the view's y axis upwards
        length = float(np.hypot(dx, up))
        if length == 0.0:
            rotation = np.eye(3)
        else:
            axis = np.array([-up, dx, 0.0]) / length  # turns depth towards the drag
            angle = length * _ROTATE_RADIANS_PER_PIXEL
            k = np.array(
                [[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]]
            )
            rotation = np.eye(3) + np.sin(angle) * k + (1 - np.cos(angle)) * (k @ k)
        self._plane = self._rotateFrame @ rotation[:2, :].T
        self._redraw()

    def endRotate(self) -> None:
        if self._rotateFrame is not None:
            # the tour carries on from the new view
            self._start, self._target, self._t = self._plane, self._randomPlane(), 0.0
        self._rotateFrame = None
        self._setCursor(
            Qt.CursorShape.CrossCursor
            if self.viewBox.lassoMode
            else Qt.CursorShape.OpenHandCursor
        )
        if self._resumeTour:
            self._timer.start()
        self._resumeTour = False

    def rotateBy(self, dx: float, dy: float) -> None:
        """One-off trackball turn by (dx, dy) screen pixels."""
        resume = self._timer.isActive()
        self.beginRotate()
        self.dragRotate(dx, dy)
        self.endRotate()
        if resume:
            self._timer.start()

    def _hiddenDirection(self) -> np.ndarray | None:
        """Unit vector, within the tour's dimensions and orthogonal to the view,
        along which the (collapsed) cloud spreads most."""
        data = self._data if self._collapse is None else self._data @ self._collapse
        sub = data[:, self._dims]
        planeSub = self._plane[self._dims]
        residual = sub - (sub @ planeSub) @ planeSub.T
        if len(self._dims) <= 2 or not np.any(residual):
            return None
        _, _, vt = np.linalg.svd(residual, full_matrices=False)
        direction = np.zeros(self._data.shape[1])
        direction[self._dims] = vt[0]
        return direction

    def axisVectors(self) -> dict[int, np.ndarray]:
        """Where each tour dimension's unit vector lands in the view (2-D)."""
        k = self._data.shape[1]
        out = {}
        for d in self._dims:
            unit = np.zeros(k)
            unit[d] = 1.0
            out[d] = self.projectPoints(unit[None, :])[0]
        return out

    def _drawAxes(self) -> None:
        for item in self._axisItems:
            self.viewBox.removeItem(item)
        self._axisItems = []
        if not self.axesBox.isChecked():
            return
        length = 0.85 * self._radius
        for d, vector in self.axisVectors().items():
            tip = vector * length
            line = pg.PlotCurveItem(
                [0.0, tip[0]], [0.0, tip[1]], pen=pg.mkPen(self.AXIS_COLOR, width=1.2)
            )
            label = pg.TextItem(str(d + 1), color=self.AXIS_COLOR, anchor=(0.5, 0.5))
            label.setPos(tip[0] * 1.08, tip[1] * 1.08)
            for item in (line, label):
                item.setZValue(-1)
                self.viewBox.addItem(item, ignoreBounds=True)
                self._axisItems.append(item)

    def newProjection(self) -> None:
        self._plane = self._randomPlane()
        self._start, self._target, self._t = self._plane, self._randomPlane(), 0.0
        self._redraw()

    def _fitView(self) -> None:
        if not self._data.size or not self._dims:
            return
        # Frame the bulk of the cloud as it looks projected (a 2-D view of many
        # dimensions is far narrower than the cloud's full radius), judged
        # over a set of random planes so the frame suits the whole tour.
        rng = np.random.default_rng(0)
        data = self._data[:, self._dims]
        spans = [
            np.percentile(np.abs(data @ randomPlane(len(self._dims), rng)), 99.5)
            for _ in range(_FIT_PLANES)
        ]
        radius = float(np.max(spans)) * 1.2
        radius = radius or 1.0
        self._radius = radius
        self.viewBox.setRange(
            xRange=(-radius, radius), yRange=(-radius, radius), padding=0
        )

    def _redraw(self) -> None:
        if self._data.shape[1] < 2:
            self.scatter.setData([], [])
            return
        self._projected = self.projectPoints(self._data)
        if len(self._brushes) != len(self._colors):  # rebuilt only when colours change
            cache = {c: pg.mkBrush(c) for c in set(self._colors)}
            self._brushes = [cache[c] for c in self._colors]
        self.scatter.setData(
            pos=self._projected,
            brush=self._brushes,
            data=self._ids,
            size=self.sizeSlider.value(),
        )
        if self._background.size:
            bg = self.projectPoints(self._background)
            self.backgroundItem.setData(pos=bg)
        self._drawAxes()
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
