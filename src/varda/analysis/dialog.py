"""Dialog to pick an image and an analysis, adjust its settings, and run it."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QComboBox, QDialog, QFormLayout, QLabel, QWidget

from varda.analysis.analysis import Analysis
from varda.common.entities import VardaRaster
from varda.common.parameter import ImageParameter
from varda.common.ui import ButtonBuilder, HBoxBuilder, SectionBox, VBoxBuilder


class RunAnalysisDialog(QDialog):
    sigRunRequested = pyqtSignal(object, object)  # (Analysis, VardaRaster)

    def __init__(
        self,
        images: Sequence[VardaRaster],
        analyses: Sequence[type[Analysis]],
        *,
        image: VardaRaster | None = None,
        analysis: type[Analysis] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        # Opened for one analysis (from its menu entry), the dialog is that
        # analysis's dialog: no picker, its name as the title.
        self.setWindowTitle(analysis.name if analysis is not None else "Run Analysis")
        self._analyses = list(analyses)
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
            .withStretch()
            .withLayout(
                HBoxBuilder()
                .withWidget(ButtonBuilder("Run").onClick(self.accept))
                .withStretch()
                .withWidget(ButtonBuilder("Cancel").onClick(self.reject))
            )
        )

        self.analysisCombo.currentIndexChanged.connect(self._showSettings)
        self._showSettings()
        self.accepted.connect(
            lambda: self.sigRunRequested.emit(
                self.selectedAnalysis(), self.selectedImage()
            )
        )

    def selectedAnalysis(self) -> Analysis:
        analysisClass = self._analyses[self.analysisCombo.currentIndex()]
        if analysisClass not in self._instances:
            self._instances[analysisClass] = analysisClass()
        return self._instances[analysisClass]

    def selectedImage(self) -> VardaRaster:
        return self.imageParam.get()

    def connectOnRun(self, callback: Callable[[Analysis, VardaRaster], None]):
        self.sigRunRequested.connect(callback)
        return self

    def _showSettings(self) -> None:
        analysis = self.selectedAnalysis()
        self.descriptionLabel.setText(analysis.description)
        if analysis.params:
            self.settingsBox.setContent(analysis.createWidget())
        else:
            self.settingsBox.setContent(QLabel("This analysis has no settings."))
