"""Run an analysis in the background with a progress dialog; results join the project."""

from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import QMessageBox, QWidget

from varda.analysis.analysis import Analysis
from varda.analysis.provenance import recordProvenance
from varda.branding.loader import BusyDialog
from varda.common.di_types import ProjectImages
from varda.common.entities import VardaRaster
from varda.image_loading.raster_writer import writeRaster
from varda.utilities.background import onMainThread, runInBackground


class AnalysisRunner(QObject):
    """Runs analyses in the background; a successful result is appended to the
    project's images."""

    sigProgress = pyqtSignal(int, str)
    sigFinished = pyqtSignal(object)  # the resulting VardaRaster
    sigFailed = pyqtSignal(object)  # the exception

    def __init__(self, images: ProjectImages, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._images = images
        self._parentWidget = parent

    def run(
        self, analysis: Analysis, image: VardaRaster, outputPath: str | None = None
    ) -> None:
        """``outputPath``: also write the result there (ENVI or GeoTIFF)."""
        # No cancel button: analyses run to completion
        dialog = BusyDialog(
            f"Running {analysis.name} on {image.name}…",
            title="Analysis",
            parent=self._parentWidget,
        )
        dialog.setValue(0)
        dialog.show()

        def onProgress(percent: int, message: str) -> None:
            dialog.setLabelText(f"{analysis.name}: {message}")
            dialog.setValue(percent)
            self.sigProgress.emit(percent, message)

        report = onMainThread(onProgress)

        def task() -> VardaRaster:
            result = analysis.run(image, report)
            recordProvenance(result, analysis, image)
            if outputPath is not None:
                report(100, f"saving to {outputPath}")
                writeRaster(result, outputPath)
            return result

        def onFinished(result: VardaRaster) -> None:
            dialog.close()
            self._images.append(result)
            self.sigFinished.emit(result)

        def onFailed(error: Exception) -> None:
            dialog.close()
            QMessageBox.critical(
                self._parentWidget,
                "Analysis failed",
                f"{analysis.name} failed:\n{error}",
            )
            self.sigFailed.emit(error)

        runInBackground(
            task, onFinished, onFailed, description=f"Analysis {analysis.name}"
        )
