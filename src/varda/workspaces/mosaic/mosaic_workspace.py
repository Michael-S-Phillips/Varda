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
from PyQt6.QtCore import Qt, QTimer
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
from varda.mosaicking.matching import (
    AutoAlignResult,
    DisplacementField,
    MatchSettings,
    applyTiePoints,
    findTiePoints,
)
from varda.mosaicking.model import DEFAULT_INLIER_PX, MosaicProject
from varda.mosaicking.seams import Seam, SeamMethod, computeSeams
from varda.mosaicking.radiometry import (
    LinearMode,
    RadiometryMethod,
    RadiometryResult,
    balance,
)
from varda.mosaicking.render import NO_SOURCE, MosaicResult, Resampling, renderMosaic
from varda.mosaicking.transforms import FitError
from varda.utilities.background import onMainThread, runInBackground
from varda.workspaces.mosaic.auto_align_dialog import AutoAlignDialog
from varda.workspaces.mosaic.panels import (
    InputsPanel,
    RadiometryPanel,
    SeamsPanel,
    TiePointPanel,
)
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
        # Each image's outlier threshold (px), as last set in Auto Align
        self._thresholds: dict[int, float] = {}

        self.canvas = MosaicCanvas()
        self.inputsPanel = InputsPanel(self.project)
        self.tiePanel = TiePointPanel(self.project)
        self.radiometryPanel = RadiometryPanel(self.project)
        self.seamsPanel = SeamsPanel(self.project)
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
        self.inputsPanel.sigAutoAlign.connect(self.openAutoAlign)
        self.radiometryPanel.sigBalance.connect(self.balance)
        self.radiometryPanel.sigCleared.connect(self.refreshPreview)
        self.seamsPanel.sigCompute.connect(self.findSeams)
        self.seamsPanel.sigEdit.connect(lambda _: self.showSeams())
        self.seamsPanel.sigCleared.connect(self._seamsChanged)
        self.seamsPanel.sigBlendChanged.connect(self.refreshPreview)
        self.canvas.sigSeamEdited.connect(self.editSeam)
        self.inputsPanel.sigExport.connect(self.export)
        self.tiePanel.sigChanged.connect(self.refreshPreview)
        self.canvas.sigNudge.connect(self.nudge)
        self._renderPreview()

    def _buildDocks(self) -> None:
        self.dockManager = ads.CDockManager(self)
        self.canvasDock = VardaDockWidget("Mosaic").withWidget(self.canvas)
        self.inputsDock = VardaDockWidget("Images").withWidget(self.inputsPanel)
        self.tieDock = VardaDockWidget("Tie Points").withWidget(self.tiePanel)
        self.radiometryDock = VardaDockWidget("Radiometry").withWidget(
            self.radiometryPanel
        )
        self.seamsDock = VardaDockWidget("Seams and Blending").withWidget(
            self.seamsPanel
        )
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
        manager.addDockWidgetTabToArea(
            self.radiometryDock, self.tieDock.dockAreaWidget()
        )
        manager.addDockWidgetTabToArea(self.seamsDock, self.tieDock.dockAreaWidget())
        self.tieDock.toggleView(True)  # Tie Points stays the front tab
        self.tieDock.setAsCurrentTab()

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

    def fit(self, key: int) -> str:
        """Fit an image to its tie points; returns (and shows) what happened."""
        message = self._fit(key)
        self.inputsPanel.setStatus(message)
        self.tiePanel.refresh()
        self.canvas.showFootprint(self.project.input(self.selectedKey()).footprint())
        self.refreshPreview()
        return message

    def _fit(self, key: int) -> str:
        try:
            self.project.fit(key, self._thresholds.get(key, DEFAULT_INLIER_PX))
        except FitError as error:
            return str(error)
        moving = self.project.input(key)
        points = [p for p in self.project.tiePointsOf(key) if p.enabled]
        kept = np.array([p.residual for p in points if p.inlier], float)
        rms = float(np.sqrt(np.mean(kept**2))) / moving.pixelSize if kept.size else 0.0
        model = moving.model.value.lower()
        outliers = len(points) - len(kept)
        counted = (
            f"{len(kept)} of {len(points)} tie points ({outliers} outliers left out)"
            if outliers
            else f"{len(points)} tie points"
        )
        return f"Fitted a {model} transform to {counted}: RMS {rms:.2f} pixels."

    # --- automatic alignment ---------------------------------------------------------

    def openAutoAlign(self, key: int) -> AutoAlignDialog:
        dialog = AutoAlignDialog(self.project, key, self)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.threshold.setValue(self._thresholds.get(key, DEFAULT_INLIER_PX))
        dialog.sigRun.connect(
            lambda moving, references, settings, threshold: self.autoAlign(
                dialog, moving, references, settings, threshold
            )
        )
        dialog.sigBandUsed.connect(
            lambda moving, band, used: self.setBandUsed(dialog, moving, band, used)
        )
        dialog.sigAddField.connect(self.addDisplacementField)
        dialog.show()
        return dialog

    def autoAlign(
        self,
        dialog: AutoAlignDialog,
        key: int,
        references: list[int],
        settings: MatchSettings,
        threshold: float,
    ) -> None:
        """Match in the background, then put the tie points in and fit them."""
        self._thresholds[key] = threshold
        progress = onMainThread(dialog.showProgress)

        def finished(result: AutoAlignResult) -> None:
            applyTiePoints(self.project, key, result)
            message = self.fit(key) if result.added else "Nothing was fitted."
            dialog.showResult(result, message)

        runInBackground(
            lambda: findTiePoints(self.project, key, references, settings, progress),
            finished,
            lambda error: dialog.showFailure(f"Auto Align failed: {error}"),
            description="Aligning a mosaic image",
        )

    def setBandUsed(
        self, dialog: AutoAlignDialog, key: int, band: int, used: bool
    ) -> None:
        """Use or leave out one band's automatic tie points, and refit."""
        for point in self.project.tiePointsOf(key):
            if point.auto and point.band == band:
                point.enabled = used
        message = self.fit(key)
        dialog.summary.setText(message)
        dialog.showBands()

    # --- radiometry ------------------------------------------------------------------

    def balance(
        self, method: RadiometryMethod, mode: LinearMode, held: frozenset[int]
    ) -> None:
        """Fit the radiometric corrections in the background, then use them."""

        def finished(result: RadiometryResult) -> None:
            self.project.applyRadiometry(result)
            self.radiometryPanel.showResult(
                result.message
                or f"Balanced with {method.value.split(' (')[0].lower()}."
            )
            self.refreshPreview()

        runInBackground(
            lambda: balance(self.project, method, mode, held),
            finished,
            lambda error: self.radiometryPanel.showResult(str(error)),
            description="Balancing a mosaic",
        )

    # --- seams -----------------------------------------------------------------------

    def findSeams(self, method: SeamMethod) -> None:
        """Find the seams in the background, then use and show them."""

        def finished(seams: list[Seam]) -> None:
            self.project.setSeams(method, seams)
            self.seamsPanel.showResult(
                f"{len(seams)} seam{'s' if len(seams) != 1 else ''} found."
                if seams
                else "No images overlap: there's nothing to split."
            )
            self._seamsChanged()

        runInBackground(
            lambda: computeSeams(self.project, method),
            finished,
            lambda error: self.seamsPanel.showResult(f"Finding seams failed: {error}"),
            description="Finding mosaic seams",
        )

    def showSeams(self) -> None:
        self.canvas.showSeams(self.project.seams, self.seamsPanel.edit.isChecked())

    def editSeam(self, index: int, region: int, outline: np.ndarray) -> None:
        """A seam outline dragged on the mosaic."""
        seam = self.project.seams[index]
        regions = list(seam.regions)
        regions[region] = outline
        self.project.seams[index] = Seam(seam.top, seam.bottom, tuple(regions))
        self.refreshPreview()

    def _seamsChanged(self) -> None:
        self.showSeams()
        self.refreshPreview()

    def addDisplacementField(self, displacement: DisplacementField) -> None:
        raster = displacementRaster(self.project, displacement)
        self.projectImages.append(raster)
        self.status.showMessage(f"Added {raster.name} to the image list.", 8000)

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
            self.radiometryPanel.refresh()
            self.seamsPanel.refresh()
            self.showSeams()
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
    visual = resampling is not Resampling.NEAREST or project.isVisual
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
        description=f"Mosaic of {', '.join(names)} ({_methods(project, resampling)})",
    )
    suffix = " (visual)" if visual else ""
    return VardaRaster(source, name=f"Mosaic of {len(names)} images{suffix}")


def displacementRaster(
    project: MosaicProject, displacement: DisplacementField
) -> VardaRaster:
    """A displacement field as an image: east and north displacement (map
    units) and match quality, on the tile grid over the overlap."""
    moving = project.input(displacement.movingKey).image.name
    reference = project.input(displacement.referenceKey).image.name
    names = ["East displacement", "North displacement", "Match quality"]
    source = ArrayDataSource(
        np.stack(
            [displacement.dx, displacement.dy, displacement.quality], axis=2
        ).astype(np.float32),
        wavelengths=np.array(names),
        wavelengthUnits="",
        bandNames=names,
        transform=displacement.transform,
        crs=project.inputs[0].image.crs,
        defaultBands=np.array([0, 0, 0]),
        extraMetadata={
            "displacement": {
                "moving": moving,
                "reference": reference,
                "units": "map units",
            }
        },
        description=f"Displacement of {moving} relative to {reference}, tile by tile",
    )
    return VardaRaster(source, name=f"Displacement of {moving} from {reference}")


def _methods(project: MosaicProject, resampling: Resampling) -> str:
    """How a mosaic was made, in a few words: its resampling and radiometry."""
    parts: list[str] = [f"{resampling.value.split(' (')[0].lower()} resampling"]
    if project.radiometryMethod is not RadiometryMethod.NONE:
        parts.append(
            f"{project.radiometryMethod.value.split(' (')[0].lower()} radiometry"
        )
    return ", ".join(parts)


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
