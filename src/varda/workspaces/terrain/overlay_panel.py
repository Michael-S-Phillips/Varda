"""The 3D Terrain workspace's overlays: images draped over part of the DEM
(not on its grid), each with its display settings, opacity and alignment.

Opacity and visibility change the view at once (sigLook); a new overlay, new
display settings or a new alignment need the textures built again
(sigRebuild); Auto Align is the workspace's job (sigAlignRequested), as it
needs the DEM and runs in the background."""

from __future__ import annotations

from collections.abc import Callable

from attrs import define, field
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from varda.common.entities import VardaRaster
from varda.common.ui import MutedLabel
from varda.image_rendering.image_renderer import ImageRenderer, RenderMode
from varda.mosaicking.transforms import TransformModel
from varda.terrain.overlays import Alignment

HILLSHADE = "DEM hillshade"
DEFAULT_OPACITY = 0.85


@define(eq=False)
class TerrainOverlay:
    image: VardaRaster
    renderer: ImageRenderer
    opacity: float = DEFAULT_OPACITY
    visible: bool = True
    alignment: Alignment = field(factory=Alignment)
    reference: str = HILLSHADE  # what Auto Align matches against (an image's name)

    @classmethod
    def of(cls, image: VardaRaster) -> TerrainOverlay:
        renderer = ImageRenderer(image=image)
        renderer.transparentNoData = True
        if image.bandCount >= 3:
            renderer.settings.mode.set(RenderMode.RGB)
        return cls(image, renderer)


class OverlayPanel(QWidget):
    sigRebuild = pyqtSignal()
    sigLook = pyqtSignal(int, float, bool)  # overlay, opacity, visible
    sigAlignRequested = pyqtSignal(int)

    def __init__(
        self,
        candidates: Callable[[], list[VardaRaster]],
        references: Callable[[], list[VardaRaster]],
        parent: QWidget | None = None,
    ):
        """``candidates``: images that may be added (georeferenced, on the
        DEM's body); ``references``: images on the DEM's grid to align to."""
        super().__init__(parent)
        self.overlays: list[TerrainOverlay] = []
        self._candidates = candidates
        self._references = references

        self.list = QListWidget()
        self.list.setToolTip(
            "Tick to show; select one to set its opacity and alignment"
        )
        self.list.itemChanged.connect(self._onItemChanged)
        self.list.currentRowChanged.connect(lambda _: self.showSelected())
        self.addButton = QToolButton()
        self.addButton.setText("Add Overlay")
        self.addButton.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.addMenu = QMenu(self.addButton)
        self.addMenu.aboutToShow.connect(self._fillAddMenu)
        self.addButton.setMenu(self.addMenu)
        remove = QPushButton("Remove")
        remove.clicked.connect(self.removeSelected)

        self.opacity = QSlider(Qt.Orientation.Horizontal)
        self.opacity.setRange(0, 100)
        self.opacity.valueChanged.connect(self._onOpacity)
        display = QPushButton("Display…")
        display.setToolTip("Its bands, stretch and color map, as in the image views")
        display.clicked.connect(self._editDisplay)
        self.referenceBox = QComboBox()
        self.referenceBox.setToolTip(
            "What Auto Align matches the overlay against: an image on the DEM's "
            "grid (its orthoimage is best) or a hillshade of the DEM"
        )
        self.referenceBox.currentTextChanged.connect(self._onReference)
        self.modelBox = QComboBox()
        for model in TransformModel:
            self.modelBox.addItem(model.value, model)
        self.modelBox.setToolTip("How the overlay may move to fit")
        self.modelBox.currentIndexChanged.connect(self._onModel)
        self.alignButton = QPushButton("Auto Align")
        self.alignButton.setToolTip(
            "Match the overlay's best band against the reference and fit the model"
        )
        self.alignButton.clicked.connect(self._requestAlign)
        self.shiftEast, self.shiftNorth = QDoubleSpinBox(), QDoubleSpinBox()
        for box in (self.shiftEast, self.shiftNorth):
            box.setRange(-1e6, 1e6)
            box.setDecimals(1)
            box.setSingleStep(5)
            box.setSuffix(" m")
            box.editingFinished.connect(self._onShift)
        reset = QPushButton("Reset Alignment")
        reset.clicked.connect(self._resetAlignment)
        self.alignment = MutedLabel("")
        self.alignment.setWordWrap(True)

        buttons = QHBoxLayout()
        buttons.addWidget(self.addButton)
        buttons.addWidget(remove)
        buttons.addStretch()
        self.details = QWidget()
        form = QFormLayout(self.details)
        form.setContentsMargins(0, 0, 0, 0)
        form.addRow("Opacity:", self.opacity)
        form.addRow("", display)
        form.addRow("Align to:", self.referenceBox)
        form.addRow("Model:", self.modelBox)
        form.addRow("", self.alignButton)
        shift = QHBoxLayout()
        shift.addWidget(self.shiftEast)
        shift.addWidget(self.shiftNorth)
        form.addRow("Shift E, N:", shift)
        form.addRow("", reset)
        form.addRow(self.alignment)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.list)
        layout.addLayout(buttons)
        layout.addWidget(self.details)
        self.showSelected()

    # --- the list ------------------------------------------------------------------

    def _fillAddMenu(self) -> None:
        self.addMenu.clear()
        shown = {id(o.image) for o in self.overlays}
        images = [i for i in self._candidates() if id(i) not in shown]
        if not images:
            action = self.addMenu.addAction(
                "No other georeferenced images of this body"
            )
            assert action is not None
            action.setEnabled(False)
        for image in images:
            self.addMenu.addAction(image.name, lambda image=image: self.add(image))

    def add(self, image: VardaRaster) -> TerrainOverlay:
        overlay = TerrainOverlay.of(image)
        references = [r.name for r in self._references() if r.bandCount == 1]
        overlay.reference = references[0] if references else HILLSHADE
        self.overlays.append(overlay)
        self._addItem(overlay)
        self.list.setCurrentRow(len(self.overlays) - 1)
        self.sigRebuild.emit()
        return overlay

    def _addItem(self, overlay: TerrainOverlay) -> None:
        item = QListWidgetItem(overlay.image.name)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(
            Qt.CheckState.Checked if overlay.visible else Qt.CheckState.Unchecked
        )
        self.list.blockSignals(True)
        self.list.addItem(item)
        self.list.blockSignals(False)

    def setOverlays(self, overlays: list[TerrainOverlay]) -> None:
        self.overlays = list(overlays)
        self.list.clear()
        for overlay in self.overlays:
            self._addItem(overlay)
        if self.overlays:
            self.list.setCurrentRow(0)
        self.showSelected()

    def removeSelected(self) -> None:
        row = self.list.currentRow()
        if 0 <= row < len(self.overlays):
            del self.overlays[row]
            self.list.takeItem(row)
            self.showSelected()
            self.sigRebuild.emit()

    def selected(self) -> TerrainOverlay | None:
        row = self.list.currentRow()
        return self.overlays[row] if 0 <= row < len(self.overlays) else None

    def _onItemChanged(self, item: QListWidgetItem) -> None:
        row = self.list.row(item)
        overlay = self.overlays[row]
        overlay.visible = item.checkState() == Qt.CheckState.Checked
        self.sigLook.emit(row, overlay.opacity, overlay.visible)

    # --- the selected overlay -----------------------------------------------------------

    def showSelected(self) -> None:
        overlay = self.selected()
        self.details.setEnabled(overlay is not None)
        if overlay is None:
            self.alignment.setText("")
            return
        for widget in (
            self.opacity,
            self.referenceBox,
            self.modelBox,
            self.shiftEast,
            self.shiftNorth,
        ):
            widget.blockSignals(True)
        self.opacity.setValue(round(overlay.opacity * 100))
        self.referenceBox.clear()
        self.referenceBox.addItems(
            [*[r.name for r in self._references() if r.bandCount == 1], HILLSHADE]
        )
        self.referenceBox.setCurrentText(overlay.reference)
        self.modelBox.setCurrentIndex(self.modelBox.findData(overlay.alignment.model))
        self.shiftEast.setValue(overlay.alignment.shift[0])
        self.shiftNorth.setValue(overlay.alignment.shift[1])
        for widget in (
            self.opacity,
            self.referenceBox,
            self.modelBox,
            self.shiftEast,
            self.shiftNorth,
        ):
            widget.blockSignals(False)
        self.showAlignment(overlay)

    def showAlignment(self, overlay: TerrainOverlay, message: str = "") -> None:
        if overlay is not self.selected():
            return
        a = overlay.alignment
        fitted = (
            f"Fitted to {a.points} tie points, RMS {a.rms:.3g} m."
            if a.points
            else "Placed by its georeferencing (not aligned yet)."
        )
        self.alignment.setText(f"{message} {fitted}".strip())

    def _onOpacity(self, value: int) -> None:
        overlay = self.selected()
        if overlay is not None:
            overlay.opacity = value / 100
            self.sigLook.emit(self.list.currentRow(), overlay.opacity, overlay.visible)

    def _onReference(self, name: str) -> None:
        overlay = self.selected()
        if overlay is not None and name:
            overlay.reference = name

    def _onModel(self, _index: int) -> None:
        overlay = self.selected()
        if overlay is not None:
            overlay.alignment.model = self.modelBox.currentData()

    def _onShift(self) -> None:
        overlay = self.selected()
        if overlay is None:
            return
        shift = (self.shiftEast.value(), self.shiftNorth.value())
        if shift != tuple(overlay.alignment.shift):
            overlay.alignment.shift = shift
            self.sigRebuild.emit()

    def _resetAlignment(self) -> None:
        overlay = self.selected()
        if overlay is not None:
            overlay.alignment = Alignment(overlay.alignment.model)
            self.showSelected()
            self.sigRebuild.emit()

    def _requestAlign(self) -> None:
        if self.selected() is not None:
            self.sigAlignRequested.emit(self.list.currentRow())

    def _editDisplay(self) -> None:
        overlay = self.selected()
        if overlay is None:
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Display: {overlay.image.name}")
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.accept)
        layout = QVBoxLayout(dialog)
        layout.addWidget(overlay.renderer.getSettingsPanel())
        layout.addWidget(buttons)
        dialog.exec()
        self.sigRebuild.emit()
