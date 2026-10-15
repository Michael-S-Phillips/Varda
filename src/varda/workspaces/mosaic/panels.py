"""The mosaic workspace's panels: the input stack (priority, visibility,
alignment) and the tie points between the selected input and a reference."""

from __future__ import annotations

import numpy as np
from PyQt6.QtCore import QPointF, Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from varda.common.ui import MutedLabel
from varda.mosaicking.model import MosaicProject, TiePoint
from varda.mosaicking.transforms import TransformModel
from varda.workspaces.mosaic.views import OUTLIER_COLOR, ImagePointView


# Rows are numbered by the vertical header; pixels are (col, row)
COLUMNS = ["Reference", "Moving", "Source", "Quality", "Residual (px)", "Use"]
USE_COLUMN = COLUMNS.index("Use")


def _kind(point: TiePoint) -> str:
    if not point.auto:
        return "manual"
    return "auto" if point.inlier else "outlier"


class InputsPanel(QWidget):
    """The images in priority order: the top one wins where they overlap."""

    sigSelected = pyqtSignal(int)  # input key
    sigChanged = pyqtSignal()  # order, visibility or alignment changed
    sigFit = pyqtSignal(int)
    sigAutoAlign = pyqtSignal(int)
    sigExport = pyqtSignal()

    def __init__(self, project: MosaicProject, parent: QWidget | None = None):
        super().__init__(parent)
        self.project = project
        self.list = QListWidget()
        self.list.currentItemChanged.connect(self._onCurrent)
        self.list.itemChanged.connect(self._onItemChanged)
        up, down = QPushButton("Move Up"), QPushButton("Move Down")
        up.clicked.connect(lambda: self._move(-1))
        down.clicked.connect(lambda: self._move(1))
        self.model = QComboBox()
        for model in TransformModel:
            self.model.addItem(model.value, model)
        self.model.currentIndexChanged.connect(self._onModel)
        autoAlign = QPushButton("Auto Align…")
        autoAlign.setToolTip(
            "Find tie points with the overlapping images automatically and fit them"
        )
        autoAlign.clicked.connect(lambda: self.sigAutoAlign.emit(self.selectedKey()))
        fit = QPushButton("Fit to Tie Points")
        fit.clicked.connect(lambda: self.sigFit.emit(self.selectedKey()))
        reset = QPushButton("Reset Alignment")
        reset.clicked.connect(self._reset)
        export = QPushButton("Export Mosaic…")
        export.clicked.connect(self.sigExport)
        self.status = MutedLabel("")
        self.status.setWordWrap(True)
        hint = MutedLabel(
            "Top wins where images overlap. Select an image and Auto Align it, use "
            "the arrow keys on the mosaic to nudge it (Shift: ×10), or place tie "
            "points below."
        )
        hint.setWordWrap(True)

        order = QHBoxLayout()
        order.addWidget(up)
        order.addWidget(down)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("<b>Images</b> (priority order)"))
        layout.addWidget(self.list, 1)
        layout.addLayout(order)
        layout.addWidget(hint)
        layout.addWidget(QLabel("<b>Alignment</b> of the selected image"))
        layout.addWidget(self.model)
        layout.addWidget(autoAlign)
        layout.addWidget(fit)
        layout.addWidget(reset)
        layout.addWidget(self.status)
        layout.addStretch(1)
        layout.addWidget(export)
        self.refresh()

    def selectedKey(self) -> int:
        item = self.list.currentItem()
        return (
            int(item.data(Qt.ItemDataRole.UserRole))
            if item
            else self.project.inputs[0].key
        )

    def refresh(self, select: int | None = None) -> None:
        select = self.selectedKey() if select is None and self.list.count() else select
        self.list.blockSignals(True)
        self.list.clear()
        for item in self.project.inputs:
            row = QListWidgetItem(item.image.name)
            row.setData(Qt.ItemDataRole.UserRole, item.key)
            row.setFlags(row.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            row.setCheckState(
                Qt.CheckState.Checked if item.visible else Qt.CheckState.Unchecked
            )
            self.list.addItem(row)
            if item.key == select:
                self.list.setCurrentItem(row)
        if self.list.currentItem() is None:
            self.list.setCurrentRow(0)
        self.list.blockSignals(False)
        self._showModel()

    def setStatus(self, text: str) -> None:
        self.status.setText(text)

    def _onCurrent(self, *_args) -> None:
        self._showModel()
        self.sigSelected.emit(self.selectedKey())

    def _showModel(self) -> None:
        model = self.project.input(self.selectedKey()).model
        self.model.blockSignals(True)
        self.model.setCurrentIndex(list(TransformModel).index(model))
        self.model.blockSignals(False)

    def _onItemChanged(self, row: QListWidgetItem) -> None:
        key = int(row.data(Qt.ItemDataRole.UserRole))
        self.project.input(key).visible = row.checkState() == Qt.CheckState.Checked
        self.sigChanged.emit()

    def _onModel(self) -> None:
        self.project.input(self.selectedKey()).model = self.model.currentData()

    def _move(self, steps: int) -> None:
        key = self.selectedKey()
        self.project.move(key, steps)
        self.refresh(select=key)
        self.sigChanged.emit()

    def _reset(self) -> None:
        self.project.resetAlignment(self.selectedKey())
        self.setStatus("Alignment reset.")
        self.sigChanged.emit()


class TiePointPanel(QWidget):
    """Tie points between the selected (moving) image and a reference: click
    a feature on the reference, then the same feature on the moving image."""

    sigChanged = pyqtSignal()

    def __init__(self, project: MosaicProject, parent: QWidget | None = None):
        super().__init__(parent)
        self.project = project
        self.movingKey = project.inputs[0].key
        self._pendingReference: tuple[float, float] | None = None
        self.reference = QComboBox()
        self.reference.currentIndexChanged.connect(self._onReference)
        self.referenceView = ImagePointView()
        self.movingView = ImagePointView()
        self.referenceView.sigClicked.connect(self._onReferenceClicked)
        self.movingView.sigClicked.connect(self._onMovingClicked)
        self.movingLabel = QLabel()
        self.hint = MutedLabel("")
        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.itemChanged.connect(self._onTableChanged)
        delete = QPushButton("Delete Selected")
        delete.clicked.connect(self._deleteSelected)
        deleteAuto = QPushButton("Delete Automatic")
        deleteAuto.setToolTip("Delete the selected image's automatic tie points")
        deleteAuto.clicked.connect(self._deleteAutomatic)

        views = QHBoxLayout()
        left, right = QVBoxLayout(), QVBoxLayout()
        top = QHBoxLayout()
        top.addWidget(QLabel("Reference:"))
        top.addWidget(self.reference, 1)
        left.addLayout(top)
        left.addWidget(self.referenceView, 1)
        right.addWidget(self.movingLabel)
        right.addWidget(self.movingView, 1)
        views.addLayout(left, 1)
        views.addLayout(right, 1)
        side = QVBoxLayout()
        side.addWidget(self.table, 1)
        buttons = QHBoxLayout()
        buttons.addWidget(delete)
        buttons.addWidget(deleteAuto)
        side.addLayout(buttons)
        views.addLayout(side, 1)
        layout = QVBoxLayout(self)
        layout.addLayout(views, 1)
        layout.addWidget(self.hint)
        self.setMoving(self.movingKey)

    def setMoving(self, key: int) -> None:
        self.movingKey = key
        self._pendingReference = None
        moving = self.project.input(key)
        self.movingLabel.setText(f"Moving: <b>{moving.image.name}</b>")
        self.movingView.setImage(moving.image)
        current = self.reference.currentData()
        self.reference.blockSignals(True)
        self.reference.clear()
        for item in self.project.inputs:
            if item.key != key:
                self.reference.addItem(item.image.name, item.key)
        index = self.reference.findData(current)
        self.reference.setCurrentIndex(index if index >= 0 else 0)
        self.reference.blockSignals(False)
        self._onReference()

    def referenceKey(self) -> int:
        return int(self.reference.currentData())

    def refresh(self) -> None:
        points = self._points()
        kinds = [_kind(p) for p in points]
        self.referenceView.showPoints(
            [p.referencePixel for p in points], self._pendingReference, kinds
        )
        self.movingView.showPoints([p.movingPixel for p in points], kinds=kinds)
        self.table.blockSignals(True)
        self.table.setRowCount(len(points))
        size = self.project.input(self.movingKey).pixelSize
        for row, point in enumerate(points):
            cells = [
                "%.1f, %.1f" % point.referencePixel,
                "%.1f, %.1f" % point.movingPixel,
                f"Auto, band {point.band + 1}"
                if point.auto and point.band is not None
                else ("Auto" if point.auto else "Manual"),
                "" if np.isnan(point.quality) else f"{point.quality:.2f}",
                "" if np.isnan(point.residual) else f"{point.residual / size:.2f}",
            ]
            for column, text in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if not point.inlier:
                    item.setForeground(QColor(OUTLIER_COLOR))
                    item.setToolTip("The last fit left this point out (an outlier)")
                self.table.setItem(row, column, item)
            use = QTableWidgetItem()
            use.setFlags(use.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            use.setCheckState(
                Qt.CheckState.Checked if point.enabled else Qt.CheckState.Unchecked
            )
            self.table.setItem(row, USE_COLUMN, use)
        self.table.blockSignals(False)
        waiting = (
            "now click the same feature on the moving image"
            if self._pendingReference
            else "click a feature on the reference"
        )
        self.hint.setText(
            f"{len(points)} tie points; {waiting}. Fit with Fit to Tie Points."
        )

    def _points(self):
        return [
            p
            for p in self.project.tiePointsOf(self.movingKey)
            if p.referenceKey == self.referenceKey()
        ]

    def _onReference(self) -> None:
        self._pendingReference = None
        if self.reference.count():
            self.referenceView.setImage(self.project.input(self.referenceKey()).image)
        self.refresh()

    def _onReferenceClicked(self, pos: QPointF) -> None:
        self._pendingReference = (pos.x(), pos.y())
        self.refresh()

    def _onMovingClicked(self, pos: QPointF) -> None:
        if self._pendingReference is None:
            self.hint.setText("Click the feature on the reference first.")
            return
        self.project.addTiePoint(
            self.movingKey,
            (pos.x(), pos.y()),
            self.referenceKey(),
            self._pendingReference,
        )
        self._pendingReference = None
        self.refresh()
        self.sigChanged.emit()

    def _onTableChanged(self, item: QTableWidgetItem) -> None:
        if item.column() == USE_COLUMN:
            self._points()[item.row()].enabled = (
                item.checkState() == Qt.CheckState.Checked
            )
            self.sigChanged.emit()

    def _deleteAutomatic(self) -> None:
        self.project.removeAutoTiePoints(self.movingKey)
        self.refresh()
        self.sigChanged.emit()

    def _deleteSelected(self) -> None:
        rows = sorted(
            {index.row() for index in self.table.selectedIndexes()}, reverse=True
        )
        points = self._points()
        for row in rows:
            self.project.tiePoints.remove(points[row])
        self.refresh()
        self.sigChanged.emit()
