"""The Mosaic workspace: the input stack on the left, the mosaic preview in
the middle, tie points underneath. The recipe (order, corrections, tie
points) is all that changes until Export renders the mosaic into the
project, with a map of which image each pixel came from."""

from __future__ import annotations

from collections.abc import MutableSequence, Sequence

import numpy as np
import PyQt6Ads as ads
from matplotlib import colormaps
from matplotlib.colors import to_hex
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QMainWindow,
    QMessageBox,
    QStatusBar,
    QWidget,
)

from varda.analysis.class_tools import classRaster
from varda.analysis.rasters import bandMetadata
from varda.common.entities import VardaRaster
from varda.common.ui import VardaDockWidget
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.mosaicking.grid import TargetGrid, defaultGrid, pixelSize
from varda.mosaicking.model import MosaicProject
from varda.mosaicking.render import NO_SOURCE, MosaicResult, Resampling, renderMosaic
from varda.mosaicking.transforms import FitError
from varda.utilities.background import runInBackground
from varda.workspaces.mosaic.panels import InputsPanel, TiePointPanel
from varda.workspaces.mosaic.views import PREVIEW_PIXELS, MosaicCanvas, displayBands

PREVIEW_DELAY_MS = 80


class ExportDialog(QDialog):
    def __init__(self, project: MosaicProject, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Export Mosaic")
        self.resampling = QComboBox()
        for option in Resampling:
            self.resampling.addItem(option.value, option)
        self.resolution = QDoubleSpinBox()
        self.resolution.setDecimals(3)
        self.resolution.setRange(1e-6, 1e9)
        self.resolution.setValue(pixelSize(project))
        self.resolution.setSuffix(" per pixel")
        self.sources = QCheckBox("Also add a map of which image each pixel came from")
        self.sources.setChecked(True)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form = QFormLayout(self)
        form.addRow("Resampling:", self.resampling)
        form.addRow("Pixel size:", self.resolution)
        form.addRow(self.sources)
        form.addRow(buttons)


class MosaicWorkspace(QMainWindow):
    def __init__(
        self,
        images: Sequence[VardaRaster],
        projectImages: MutableSequence[VardaRaster] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.images = list(images)
        self.project = MosaicProject(
            self.images
        )  # raises MosaicError for unusable inputs
        self.projectImages = projectImages if projectImages is not None else []
        self.setWindowTitle(f"Mosaic of {len(self.images)} images")
        self._bands = displayBands(self.images[0])
        self._cache: dict[int, np.ndarray] = {}

        self.canvas = MosaicCanvas()
        self.inputsPanel = InputsPanel(self.project)
        self.tiePanel = TiePointPanel(self.project)
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self._previewTimer = QTimer(self)
        self._previewTimer.setSingleShot(True)
        self._previewTimer.setInterval(PREVIEW_DELAY_MS)
        self._previewTimer.timeout.connect(self._renderPreview)
        self._buildDocks()

        self.inputsPanel.sigSelected.connect(self._onSelected)
        self.inputsPanel.sigChanged.connect(self.refreshPreview)
        self.inputsPanel.sigFit.connect(self.fit)
        self.inputsPanel.sigExport.connect(self.export)
        self.tiePanel.sigChanged.connect(self.refreshPreview)
        self.canvas.sigNudge.connect(self.nudge)
        self._renderPreview()

    def _buildDocks(self) -> None:
        self.dockManager = ads.CDockManager(self)
        self.canvasDock = VardaDockWidget("Mosaic").withWidget(self.canvas)
        self.inputsDock = VardaDockWidget("Images").withWidget(self.inputsPanel)
        self.tieDock = VardaDockWidget("Tie Points").withWidget(self.tiePanel)
        manager = self.dockManager
        manager.addDockWidget(ads.DockWidgetArea.CenterDockWidgetArea, self.canvasDock)
        manager.addDockWidget(
            ads.DockWidgetArea.LeftDockWidgetArea,
            self.inputsDock,
            self.canvasDock.dockAreaWidget(),
        )
        manager.addDockWidget(
            ads.DockWidgetArea.BottomDockWidgetArea,
            self.tieDock,
            self.canvasDock.dockAreaWidget(),
        )

    # --- preview -------------------------------------------------------------------

    def selectedKey(self) -> int:
        return self.inputsPanel.selectedKey()

    def refreshPreview(self) -> None:
        self._previewTimer.start()

    def previewGrid(self) -> TargetGrid:
        full = defaultGrid(self.project)
        factor = max(1.0, max(full.width, full.height) / PREVIEW_PIXELS)
        return (
            defaultGrid(self.project, pixelSize(self.project) * factor)
            if factor > 1
            else full
        )

    def _renderPreview(self) -> None:
        grid = self.previewGrid()
        result = renderMosaic(
            self.project, grid, visibleOnly=True, bands=self._bands, cache=self._cache
        )
        self.canvas.showPreview(result.cube, grid)
        self.canvas.showFootprint(self.project.input(self.selectedKey()).footprint())

    def _onSelected(self, key: int) -> None:
        self.tiePanel.setMoving(key)
        self.canvas.showFootprint(self.project.input(key).footprint())

    # --- aligning ----------------------------------------------------------------------

    def nudge(self, right: int, up: int) -> None:
        """Shift the selected image by output pixels (up is north, or up on screen)."""
        size = pixelSize(self.project)
        northUp = defaultGrid(self.project).transform.e < 0
        dy = up * size if northUp else -up * size
        key = self.selectedKey()
        self.project.nudge(key, right * size, dy)
        self.status.showMessage(
            f"Nudged {self.project.input(key).image.name} by ({right}, {up}) pixels.",
            3000,
        )
        self.refreshPreview()

    def fit(self, key: int) -> None:
        try:
            residuals = self.project.fit(key)
        except FitError as error:
            self.inputsPanel.setStatus(str(error))
            return
        size = pixelSize(self.project)
        rms = float(np.sqrt(np.mean(residuals**2))) / size if len(residuals) else 0.0
        model = self.project.input(key).model.value.lower()
        self.inputsPanel.setStatus(
            f"Fitted a {model} transform to {len(residuals)} tie points: RMS {rms:.2f} pixels."
        )
        self.tiePanel.refresh()
        self.refreshPreview()

    # --- export --------------------------------------------------------------------------

    def export(self) -> None:
        dialog = ExportDialog(self.project, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        resampling = dialog.resampling.currentData()
        grid = defaultGrid(self.project, dialog.resolution.value())
        withSources = dialog.sources.isChecked()
        self.status.showMessage("Rendering the mosaic…")
        runInBackground(
            lambda: renderMosaic(self.project, grid, resampling),
            lambda result: self._exported(result, grid, resampling, withSources),
            self._exportFailed,
            description="Rendering a mosaic",
        )

    def _exported(
        self,
        result: MosaicResult,
        grid: TargetGrid,
        resampling: Resampling,
        withSources: bool,
    ) -> None:
        mosaic = mosaicRaster(self.project, result, grid, resampling)
        self.projectImages.append(mosaic)
        if withSources:
            self.projectImages.append(sourcesRaster(self.project, result, mosaic))
        self.status.showMessage(f"Added {mosaic.name} to the image list.", 8000)

    def _exportFailed(self, error: Exception) -> None:
        self.status.clearMessage()
        QMessageBox.warning(self, "Export Mosaic", str(error))

    # --- sessions ----------------------------------------------------------------------------

    def sessionState(self) -> dict:
        return {"recipe": self.project.state()}

    def restoreSessionState(self, state: dict) -> None:
        recipe = state.get("recipe")
        if recipe:
            self.project.restore(recipe)
            self.inputsPanel.refresh()
            self.tiePanel.setMoving(self.selectedKey())
            self.refreshPreview()


def mosaicRaster(
    project: MosaicProject,
    result: MosaicResult,
    grid: TargetGrid,
    resampling: Resampling,
) -> VardaRaster:
    """The rendered mosaic as a project image, with its recipe in the metadata."""
    first = project.inputs[0].image
    visual = resampling is not Resampling.NEAREST
    names = [i.image.name for i in project.inputs]
    source = ArrayDataSource(
        result.cube,
        wavelengths=np.asarray(first.wavelengths),
        wavelengthUnits=first.wavelengthUnits,
        bandNames=list(first.bandNames),
        transform=grid.transform,
        crs=grid.crs,
        defaultBands=np.asarray(first.defaultBands),
        extraMetadata={
            **bandMetadata(first),
            "mosaic": {
                "inputs": names,
                "resampling": resampling.name,
                "recipe": project.state(),
            },
        },
        description=f"Mosaic of {', '.join(names)} ({resampling.value.split(' (')[0].lower()} resampling)",
    )
    suffix = " (visual)" if visual else ""
    return VardaRaster(source, name=f"Mosaic of {len(names)} images{suffix}")


def sourcesRaster(
    project: MosaicProject, result: MosaicResult, mosaic: VardaRaster
) -> VardaRaster:
    """Which input each mosaic pixel came from, as a class map."""
    classes = np.where(result.sources == NO_SOURCE, np.nan, result.sources).astype(
        np.float32
    )
    names = [i.image.name for i in project.inputs]
    ramp = colormaps["tab10"]
    colors = [to_hex(ramp(k % 10)) for k in range(len(names))]
    return classRaster(
        mosaic,
        classes,
        names,
        colors,
        name=f"{mosaic.name} sources",
        description=f"Source image of each pixel of {mosaic.name}",
    )
