"""Dialog to pick an image and an analysis, adjust its settings, and run it."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QWidget,
)

from varda.analysis.analysis import Analysis, AnalysisContext
from varda.common.entities import VardaRaster
from varda.common.parameter import ImageParameter
from varda.common.ui import ButtonBuilder, HBoxBuilder, SectionBox, VBoxBuilder
from varda.image_loading.raster_writer import SAVE_FILE_FILTER, suggestedOutputPath
from varda.rois.roi_collection import ROICollection


class RunAnalysisDialog(QDialog):
    # (Analysis, VardaRaster, output file path or None)
    sigRunRequested = pyqtSignal(object, object, object)

    def __init__(
        self,
        images: Sequence[VardaRaster],
        analyses: Sequence[type[Analysis]],
        *,
        image: VardaRaster | None = None,
        analysis: type[Analysis] | None = None,
        rois: ROICollection | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """``rois``: the current workspace's ROI collection, handed to analyses
        that train on or use ROIs."""
        super().__init__(parent)
        # Opened for one analysis (from its menu entry), the dialog is that
        # analysis's dialog: no picker, its name as the title.
        self.setWindowTitle(analysis.name if analysis is not None else "Run Analysis")
        self._analyses = list(analyses)
        self._context = AnalysisContext(rois=rois)
        # One instance per analysis class, so settings persist while switching
        self._instances: dict[type[Analysis], Analysis] = {}

        self.imageParam = ImageParameter("Image", "The image to analyse")
        self.imageParam.setProvider(lambda: list(images))
        if image is not None:
            self.imageParam.set(image)

        self.analysisCombo = QComboBox()
        self.analysisCombo.addItems([a.name for a in self._analyses])
        if analysis is not None and analysis in self._analyses:
            self.analysisCombo.setCurrentIndex(self._analyses.index(analysis))

        self.descriptionLabel = QLabel()
        self.descriptionLabel.setWordWrap(True)
        self.descriptionLabel.setStyleSheet("color: palette(mid);")
        self.settingsBox = SectionBox("Settings")
        # Analyses may offer a widget that helps choose their settings
        self.previewBox = SectionBox("Preview")

        # Output: the result always joins the project; optionally it is also
        # written to disk.
        self.saveCheck = QCheckBox("Save result to file")
        self.pathEdit = QLineEdit()
        self.pathEdit.setPlaceholderText("ENVI (.img / .hdr) or GeoTIFF (.tif)")
        self.browseButton = ButtonBuilder("Browse…").onClick(self._browse)
        outputBox = SectionBox("Output")
        outputContent = QWidget()
        outputContent.setLayout(
            VBoxBuilder(margins=0)
            .withWidget(self.saveCheck)
            .withLayout(
                HBoxBuilder(margins=0)
                .withWidget(self.pathEdit)
                .withWidget(self.browseButton)
            )
        )
        outputBox.setContent(outputContent)

        # Why Run is unavailable (e.g. the analysis needs ROIs and there are none)
        self.statusLabel = QLabel()
        self.statusLabel.setWordWrap(True)
        self.runButton = ButtonBuilder("Run").onClick(self.accept)

        form = QFormLayout()
        form.addRow("Image", self.imageParam.getWidget())
        form.addRow("Analysis", self.analysisCombo)
        if analysis is not None:
            form.setRowVisible(self.analysisCombo, False)
        self.setLayout(
            VBoxBuilder(Qt.AlignmentFlag.AlignTop)
            .withLayout(form)
            .withWidget(self.descriptionLabel)
            .withWidget(self.settingsBox)
            .withWidget(self.previewBox)
            .withWidget(outputBox)
            .withWidget(self.statusLabel)
            .withStretch()
            .withLayout(
                HBoxBuilder()
                .withWidget(self.runButton)
                .withStretch()
                .withWidget(ButtonBuilder("Cancel").onClick(self.reject))
            )
        )

        self.analysisCombo.currentIndexChanged.connect(self._showSettings)
        self.imageParam.sigParameterChanged.connect(lambda _: self._showSettings())
        self.saveCheck.toggled.connect(self._updateRunState)
        self.pathEdit.textChanged.connect(self._updateRunState)
        self._showSettings()
        self.accepted.connect(
            lambda: self.sigRunRequested.emit(
                self.selectedAnalysis(), self.selectedImage(), self.outputPath()
            )
        )

    def selectedAnalysis(self) -> Analysis:
        analysisClass = self._analyses[self.analysisCombo.currentIndex()]
        if analysisClass not in self._instances:
            self._instances[analysisClass] = analysisClass()
        return self._instances[analysisClass]

    def selectedImage(self) -> VardaRaster:
        return self.imageParam.get()

    def outputPath(self) -> str | None:
        """Where to save the result, or None to only add it to the project."""
        path = self.pathEdit.text().strip()
        return path if self.saveCheck.isChecked() and path else None

    def connectOnRun(
        self, callback: Callable[[Analysis, VardaRaster, str | None], None]
    ):
        self.sigRunRequested.connect(callback)
        return self

    def _browse(self) -> None:
        image = self.selectedImage()
        start = self.pathEdit.text().strip() or (
            str(
                suggestedOutputPath(
                    image, f"{image.name} {self.selectedAnalysis().name}"
                )
            )
            if image is not None
            else ""
        )
        path, _ = QFileDialog.getSaveFileName(
            self, "Save result as", start, SAVE_FILE_FILTER
        )
        if path:
            self.pathEdit.setText(str(Path(path)))
            self.saveCheck.setChecked(True)

    def _showSettings(self) -> None:
        analysis = self.selectedAnalysis()
        analysis.setContext(self._context)
        image = self.selectedImage()
        if image is not None:
            analysis.prepareFor(image)
        self.descriptionLabel.setText(analysis.description)
        if analysis.params:
            self.settingsBox.setContent(analysis.createWidget())
        else:
            self.settingsBox.setContent(QLabel("This analysis has no settings."))
        preview = analysis.createPreviewWidget(image) if image is not None else None
        self.previewBox.setContent(preview)
        self.previewBox.setVisible(preview is not None)
        self._updateRunState()

    def _updateRunState(self) -> None:
        analysis = self.selectedAnalysis()
        image = self.selectedImage()
        rois = self._context.rois
        if image is not None and analysis.unavailableReason(image):
            reason = analysis.unavailableReason(image)
        elif analysis.needsRois and (rois is None or len(rois) == 0):
            reason = (
                "This analysis trains on ROIs: open the image in a workspace and "
                "draw at least two ROIs first."
            )
        elif self.saveCheck.isChecked() and not self.pathEdit.text().strip():
            reason = (
                "Enter a file path for the result, or untick “Save result to file”."
            )
        else:
            reason = ""
        self.runButton.setEnabled(not reason)
        self.statusLabel.setText(reason)
