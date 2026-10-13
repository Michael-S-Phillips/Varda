"""ROI drawing controls.

- ``ROIShapePicker`` (in the ROI manager): freehand, polygon, rectangle or
  ellipse for the next shapes.
- ``ROIClassPicker``: which class the next shapes join, and New Class. It sits
  in the ROI manager and also under a view while drawing there.
- ``ROIDrawingController`` ties the Draw ROI tool of each view's toolbar to the
  shared ``ROIDrawingState``.
"""

from __future__ import annotations

import math

from collections.abc import Sequence

from PyQt6.QtCore import QObject, QPointF, QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QWidget,
)

from varda.common.entities import Color, ROIMode
from varda.image_rendering.raster_view.viewport_tools.roi_tools import ROIDrawTool
from varda.image_rendering.raster_view.viewport_tools.tool_manager import ToolManager
from varda.image_rendering.raster_view.viewport_tools.viewport_tool import ViewportTool
from varda.rois.roi_drawing_state import ROIDrawingState

SHAPES = {
    ROIMode.FREEHAND: ("Freehand", "Press and drag around the area"),
    ROIMode.POLYGON: (
        "Polygon",
        "Click each corner; double-click or Enter to finish, Backspace to undo a corner",
    ),
    ROIMode.RECTANGLE: ("Rectangle", "Drag from corner to corner"),
    ROIMode.ELLIPSE: ("Ellipse", "Drag across the ellipse's bounding box"),
}
ICON_SIZE = 22


def _shapeIcon(shape: ROIMode, color: QColor) -> QIcon:
    size = ICON_SIZE * 2  # drawn at 2x for sharp high-DPI icons
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(color, 3))
    box = QRectF(5, 7, size - 10, size - 14)
    if shape == ROIMode.RECTANGLE:
        painter.drawRect(box)
    elif shape == ROIMode.ELLIPSE:
        painter.drawEllipse(box)
    elif shape == ROIMode.POLYGON:
        points = [(5, 26), (12, 7), (30, 11), (31, 29), (17, 24)]
        painter.drawPolygon(*[QPointF(x, y) for x, y in points])
    else:  # an irregular blob, smoothed through the midpoints of its corners
        centre, radius = size / 2, size / 2 - 5
        corners = [
            QPointF(
                centre + radius * r * math.cos(2 * math.pi * k / 8),
                centre + radius * r * math.sin(2 * math.pi * k / 8),
            )
            for k, r in enumerate((1.0, 0.72, 0.95, 0.6, 0.9, 0.8, 1.0, 0.55))
        ]
        mids = [(a + b) / 2 for a, b in zip(corners, corners[1:] + corners[:1])]
        path = QPainterPath(mids[-1])
        for corner, mid in zip(corners, mids):
            path.quadTo(corner, mid)
        painter.drawPath(path)
    painter.end()
    pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)


def _swatch(color: Color) -> QIcon:
    pixmap = QPixmap(14, 14)
    qcolor = color.toQColor()
    qcolor.setAlpha(255)
    pixmap.fill(qcolor)
    return QIcon(pixmap)


class ROIShapePicker(QWidget):
    def __init__(self, state: ROIDrawingState, parent: QWidget | None = None):
        super().__init__(parent)
        self.state = state
        self.buttons: dict[ROIMode, QToolButton] = {}
        group = QButtonGroup(self)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        textColor = self.palette().windowText().color()
        for shape, (label, tip) in SHAPES.items():
            button = QToolButton()
            button.setToolTip(f"{label}: {tip}")
            button.setAccessibleName(label)
            button.setIcon(_shapeIcon(shape, textColor))
            button.setIconSize(QSize(ICON_SIZE, ICON_SIZE))
            button.setCheckable(True)
            button.clicked.connect(lambda _, s=shape: state.setShape(s))
            group.addButton(button)
            layout.addWidget(button)
            self.buttons[shape] = button
        layout.addStretch()
        state.sigShapeChanged.connect(self._sync)
        self._sync(state.shape)

    def _sync(self, shape: ROIMode) -> None:
        self.buttons[shape].setChecked(True)


class ROIClassPicker(QWidget):
    """The class the next shapes join, with New Class."""

    def __init__(
        self,
        state: ROIDrawingState,
        label: str = "Class:",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.state = state
        self.classBox = QComboBox()
        self.classBox.setMinimumContentsLength(12)
        self.classBox.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.classBox.setPlaceholderText("first shape starts Class 1")
        self.classBox.setToolTip(
            "New shapes join this class. ROIs that share a name are one class "
            "(e.g. for training a classifier)."
        )
        self.newButton = QToolButton()
        self.newButton.setText("New Class")
        self.newButton.setToolTip("Start a new class for the next shapes")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        if label:
            layout.addWidget(QLabel(label))
        layout.addWidget(self.classBox, 1)
        layout.addWidget(self.newButton)

        self.newButton.clicked.connect(lambda: state.newClass())
        self.classBox.currentIndexChanged.connect(self._onChosen)
        state.sigClassesChanged.connect(self._refresh)
        state.sigActiveClassChanged.connect(lambda _: self._refresh())
        self._refresh()

    def _refresh(self) -> None:
        self.classBox.blockSignals(True)
        self.classBox.clear()
        for roiClass in self.state.classes():
            count = roiClass.count or "new"
            self.classBox.addItem(
                _swatch(roiClass.color), f"{roiClass.name} ({count})", roiClass.name
            )
        self.classBox.setCurrentIndex(self.classBox.findData(self.state.activeClass))
        self.classBox.blockSignals(False)

    def _onChosen(self, index: int) -> None:
        name = self.classBox.itemData(index)
        if name is not None:
            self.state.setActiveClass(name)


class ROIDrawingController(QObject):
    """Feeds the shared drawing state to the Draw ROI tool of each view, adds
    finished shapes to the active class, and shows a class picker under the
    view being drawn on."""

    def __init__(
        self,
        state: ROIDrawingState,
        toolManagers: Sequence[ToolManager],
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self.state = state
        self._classBars: dict[ToolManager, ROIClassPicker] = {}
        for manager in toolManagers:
            # Its own row under the view, so a narrow toolbar can't hide it
            bar = ROIClassPicker(state, label="Drawing into:")
            bar.setVisible(False)
            manager.viewport.addToolBar(bar)
            self._classBars[manager] = bar
            manager.sigToolActivated.connect(
                lambda tool, m=manager: self._onActivated(m, tool)
            )
            manager.sigToolDeactivated.connect(
                lambda tool, m=manager: self._onDeactivated(m, tool)
            )

    def classBarVisible(self, manager: ToolManager) -> bool:
        return self._classBars[manager].isVisibleTo(manager.viewport)

    def _onActivated(self, manager: ToolManager, tool: ViewportTool) -> None:
        if not isinstance(tool, ROIDrawTool):
            return
        tool.setShape(self.state.shape)
        self.state.sigShapeChanged.connect(tool.setShape)
        tool.sigROIDrawingComplete.connect(
            lambda result: self.state.addDrawnShape(
                result["geometry"], result["roiType"]
            )
        )
        self._classBars[manager].setVisible(True)

    def _onDeactivated(self, manager: ToolManager, tool: ViewportTool) -> None:
        if not isinstance(tool, ROIDrawTool):
            return
        self.state.sigShapeChanged.disconnect(tool.setShape)
        self._classBars[manager].setVisible(False)
