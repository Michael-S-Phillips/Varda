"""The mosaic workspace's panels: the input stack (priority, visibility,
alignment) and the tie points between the selected input and a reference."""

from __future__ import annotations

import numpy as np
from PyQt6.QtCore import QPointF, Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFormLayout,
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
from varda.mosaicking.recipe import (
    Correction,
    LinearMode,
    RadiometryMethod,
    SeamMethod,
)
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


def _perBand(correction: Correction, shown: int = 12) -> str:
    """Each band's gain and offset, for a tooltip."""
    if correction.lutIn is not None:
        return "Histogram matching: a lookup table per band"
    lines = [
        f"Band {b + 1}: gain {g:.4f}, offset {o:.4g}"
        for b, (g, o) in enumerate(zip(correction.gain, correction.offset))
    ]
    more = len(lines) - shown
    return "\n".join(lines[:shown] + ([f"… and {more} more bands"] if more > 0 else []))


class RadiometryPanel(QWidget):
    """Balancing the images' brightness from their overlaps, per band."""

    # (method, mode, held keys)
    sigBalance = pyqtSignal(object, object, object)
    sigCleared = pyqtSignal()

    def __init__(self, project: MosaicProject, parent: QWidget | None = None):
        super().__init__(parent)
        self.project = project
        self.method = QComboBox()
        for method in RadiometryMethod:
            self.method.addItem(method.value, method)
        self.method.currentIndexChanged.connect(lambda _: self._updateState())
        self.mode = QComboBox()
        for mode in LinearMode:
            self.mode.addItem(mode.value, mode)
        self.held = QListWidget()
        self.held.setToolTip(
            "Held images keep their values; the others are matched to them"
        )
        self.balanceButton = QPushButton("Balance")
        self.balanceButton.clicked.connect(self._balance)
        clear = QPushButton("Clear")
        clear.setToolTip("Remove the corrections: every image keeps its values")
        clear.clicked.connect(self._clear)
        self.status = MutedLabel("")
        self.status.setWordWrap(True)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Image", "Gain (mean)", "Offset (mean)"])
        header = self.table.horizontalHeader()
        assert header is not None
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        note = MutedLabel(
            "Linear corrections are documented per band and recorded with the "
            "mosaic; with None every spectrum stays exact. Histogram matching "
            "changes spectral shape, so its mosaic is labeled visual."
        )
        note.setWordWrap(True)

        form = QFormLayout()
        form.addRow("Method:", self.method)
        form.addRow("Fit:", self.mode)
        left = QVBoxLayout()
        left.addLayout(form)
        left.addWidget(QLabel("Held images:"))
        left.addWidget(self.held, 1)
        buttons = QHBoxLayout()
        buttons.addWidget(self.balanceButton)
        buttons.addWidget(clear)
        buttons.addStretch()
        left.addLayout(buttons)
        left.addWidget(self.status)
        right = QVBoxLayout()
        right.addWidget(self.table, 1)
        right.addWidget(note)
        layout = QHBoxLayout(self)
        layout.addLayout(left, 1)
        layout.addLayout(right, 1)
        self.refresh()

    def refresh(self) -> None:
        """Show the project's radiometry: its method, held images and corrections."""
        self.method.blockSignals(True)
        self.method.setCurrentIndex(
            list(RadiometryMethod).index(self.project.radiometryMethod)
        )
        self.method.blockSignals(False)
        self.mode.setCurrentIndex(list(LinearMode).index(self.project.radiometryMode))
        held = self.project.heldKeys or {self.project.inputs[0].key}
        self.held.clear()
        for item in self.project.inputs:
            row = QListWidgetItem(item.image.name)
            row.setData(Qt.ItemDataRole.UserRole, item.key)
            row.setFlags(row.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            row.setCheckState(
                Qt.CheckState.Checked if item.key in held else Qt.CheckState.Unchecked
            )
            self.held.addItem(row)
        self.table.setRowCount(len(self.project.inputs))
        for row, item in enumerate(self.project.inputs):
            correction = item.radiometry
            if correction is None:
                cells = [item.image.name, "—", "—"]
            elif correction.lutIn is not None:
                cells = [item.image.name, "histogram", "histogram"]
            else:
                cells = [
                    item.image.name,
                    f"{np.mean(correction.gain):.4f}",
                    f"{np.mean(correction.offset):.4g}",
                ]
            tip = _perBand(correction) if correction is not None else ""
            for column, text in enumerate(cells):
                cell = QTableWidgetItem(text)
                cell.setToolTip(tip)
                self.table.setItem(row, column, cell)
        self._updateState()

    def heldKeys(self) -> frozenset[int]:
        return frozenset(
            int(self.held.item(row).data(Qt.ItemDataRole.UserRole))
            for row in range(self.held.count())
            if self.held.item(row).checkState() == Qt.CheckState.Checked
        )

    def _updateState(self) -> None:
        method = self.method.currentData()
        self.mode.setEnabled(
            method in (RadiometryMethod.REFERENCE, RadiometryMethod.GLOBAL)
        )
        self.held.setEnabled(method is not RadiometryMethod.NONE)

    def showResult(self, message: str) -> None:
        self.balanceButton.setEnabled(True)
        self.status.setText(message)
        self.refresh()

    def _balance(self) -> None:
        method = self.method.currentData()
        if method is RadiometryMethod.NONE:
            self._clear()
            return
        held = self.heldKeys()
        if not held:
            self.status.setText(
                "Hold at least one image: the others are matched to it."
            )
            return
        self.balanceButton.setEnabled(False)
        self.status.setText("Balancing…")
        self.sigBalance.emit(method, self.mode.currentData(), held)

    def _clear(self) -> None:
        self.project.clearRadiometry()
        self.status.setText("No corrections: every image keeps its values.")
        self.refresh()
        self.sigCleared.emit()


class SeamsPanel(QWidget):
    """Where each image takes over in an overlap."""

    sigCompute = pyqtSignal(object)  # SeamMethod
    sigEdit = pyqtSignal(bool)
    sigCleared = pyqtSignal()

    def __init__(self, project: MosaicProject, parent: QWidget | None = None):
        super().__init__(parent)
        self.project = project
        self.method = QComboBox()
        for method in SeamMethod:
            self.method.addItem(method.value, method)
        self.computeButton = QPushButton("Find Seams")
        self.computeButton.clicked.connect(self._compute)
        self.edit = QPushButton("Edit on Mosaic")
        self.edit.setCheckable(True)
        self.edit.setToolTip(
            "Drag the corners of the seam outlines on the mosaic; double-click "
            "an edge to add a corner"
        )
        self.edit.toggled.connect(self.sigEdit)
        clear = QPushButton("Clear")
        clear.setToolTip("Back to the stack order: the top image wins in every overlap")
        clear.clicked.connect(self._clear)
        self.status = MutedLabel("")
        self.status.setWordWrap(True)
        note = MutedLabel(
            "Seams only decide which image each pixel comes from, so spectra "
            "stay exact. Voronoi splits each overlap down its middle; least "
            "difference follows where the images agree, so the seam is hard to "
            "see. Find seams again after changing the alignment."
        )
        note.setWordWrap(True)
        form = QFormLayout()
        form.addRow("Method:", self.method)
        buttons = QHBoxLayout()
        buttons.addWidget(self.computeButton)
        buttons.addWidget(self.edit)
        buttons.addWidget(clear)
        buttons.addStretch()
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(buttons)
        layout.addWidget(self.status)
        layout.addWidget(note)
        layout.addStretch(1)
        self.refresh()

    def refresh(self) -> None:
        self.method.setCurrentIndex(list(SeamMethod).index(self.project.seamMethod))
        self.edit.setEnabled(bool(self.project.seams))
        if not self.project.seams and self.edit.isChecked():
            self.edit.setChecked(False)

    def showResult(self, message: str) -> None:
        self.computeButton.setEnabled(True)
        self.status.setText(message)
        self.refresh()

    def _compute(self) -> None:
        method = self.method.currentData()
        if method is SeamMethod.PRIORITY:
            self._clear()
            return
        self.computeButton.setEnabled(False)
        self.status.setText("Finding seams…")
        self.sigCompute.emit(method)

    def _clear(self) -> None:
        self.project.clearSeams()
        self.status.setText("The stack order decides: the top image wins.")
        self.refresh()
        self.sigCleared.emit()
