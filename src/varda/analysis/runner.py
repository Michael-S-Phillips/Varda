"""Run an analysis in the background with a progress dialog; results join the project."""

from __future__ import annotations

import logging

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal
from PyQt6.QtWidgets import QMessageBox, QProgressDialog, QWidget

from varda.analysis.analysis import Analysis
from varda.common.di_types import ProjectImages
from varda.common.entities import VardaRaster
from varda.image_loading.raster_writer import writeRaster

logger = logging.getLogger(__name__)


class _JobSignals(QObject):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(object)  # VardaRaster
    failed = pyqtSignal(object)  # Exception


class _AnalysisJob(QRunnable):
    def __init__(
        self, analysis: Analysis, image: VardaRaster, outputPath: str | None
    ) -> None:
        super().__init__()
        self.analysis = analysis
        self.image = image
        self.outputPath = outputPath
        self.signals = _JobSignals()

    def run(self) -> None:
        try:
            result = self.analysis.run(self.image, self.signals.progress.emit)
            if self.outputPath is not None:
                self.signals.progress.emit(100, f"saving to {self.outputPath}")
                writeRaster(result, self.outputPath)
        except Exception as error:  # reported to the user by the runner
            logger.exception("Analysis %s failed", self.analysis.name)
            self.signals.failed.emit(error)
            return
        self.signals.finished.emit(result)


class AnalysisRunner(QObject):
    """Runs analyses on the global thread pool; a successful result is appended
    to the project's images."""

    sigProgress = pyqtSignal(int, str)
    sigFinished = pyqtSignal(object)  # the resulting VardaRaster
    sigFailed = pyqtSignal(object)  # the exception

    def __init__(self, images: ProjectImages, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._images = images
        self._parentWidget = parent
        self._jobs: list[_AnalysisJob] = []  # keep running jobs alive

    def run(
        self, analysis: Analysis, image: VardaRaster, outputPath: str | None = None
    ) -> None:
        """``outputPath``: also write the result there (ENVI or GeoTIFF)."""
        dialog = QProgressDialog(
            f"Running {analysis.name} on {image.name}…",
            None,  # no cancel button: analyses run to completion
            0,
            100,
            self._parentWidget,
        )
        dialog.setWindowTitle("Analysis")
        dialog.setMinimumDuration(0)
        dialog.setValue(0)

        job = _AnalysisJob(analysis, image, outputPath)
        self._jobs.append(job)

        def onProgress(percent: int, message: str) -> None:
            dialog.setLabelText(f"{analysis.name}: {message}")
            dialog.setValue(percent)
            self.sigProgress.emit(percent, message)

        def onFinished(result: VardaRaster) -> None:
            dialog.close()
            self._jobs.remove(job)
            self._images.append(result)
            self.sigFinished.emit(result)

        def onFailed(error: Exception) -> None:
            dialog.close()
            self._jobs.remove(job)
            QMessageBox.critical(
                self._parentWidget,
                "Analysis failed",
                f"{analysis.name} failed:\n{error}",
            )
            self.sigFailed.emit(error)

        job.signals.progress.connect(onProgress)
        job.signals.finished.connect(onFinished)
        job.signals.failed.connect(onFailed)
        pool = QThreadPool.globalInstance()
        assert pool is not None
        pool.start(job)
