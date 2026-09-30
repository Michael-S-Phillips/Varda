"""Export Image: pick an image and a destination, then write it in the background."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QProgressDialog,
    QWidget,
)

from varda.common.entities import VardaRaster
from varda.common.parameter import ImageParameter
from varda.common.ui import ButtonBuilder, HBoxBuilder, VBoxBuilder
from varda.image_loading.raster_writer import (
    SAVE_FILE_FILTER,
    suggestedOutputPath,
    writeRaster,
)

logger = logging.getLogger(__name__)


class _WriteSignals(QObject):
    finished = pyqtSignal(object, str)  # (VardaRaster, path)
    failed = pyqtSignal(object)  # Exception


class _WriteJob(QRunnable):
    def __init__(self, image: VardaRaster, path: str) -> None:
        super().__init__()
        self.image = image
        self.path = path
        self.signals = _WriteSignals()

    def run(self) -> None:
        try:
            writeRaster(self.image, self.path)
        except Exception as error:  # reported to the user by the caller
            logger.exception("Writing %s to %s failed", self.image.name, self.path)
            self.signals.failed.emit(error)
            return
        self.signals.finished.emit(self.image, self.path)


class ExportImageDialog(QDialog):
    sigExported = pyqtSignal(object, str)  # (VardaRaster, path written)

    def __init__(
        self,
        images: Sequence[VardaRaster],
        *,
        image: VardaRaster | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Export Image")
        self._jobs: list[_WriteJob] = []  # keep running writes alive

        self.imageParam = ImageParameter("Image", "The image to write")
        self.imageParam.setProvider(lambda: list(images))
        if image is not None:
            self.imageParam.set(image)

        self.pathEdit = QLineEdit()
        self.pathEdit.setPlaceholderText("ENVI (.img / .hdr) or GeoTIFF (.tif)")
        self.browseButton = ButtonBuilder("Browse…").onClick(self._browse)
        self.exportButton = ButtonBuilder("Export").onClick(self.accept)

        form = QFormLayout()
        form.addRow("Image", self.imageParam.getWidget())
        form.addRow(
            "Save as",
            HBoxBuilder(margins=0)
            .withWidget(self.pathEdit)
            .withWidget(self.browseButton),
        )
        self.setLayout(
            VBoxBuilder()
            .withLayout(form)
            .withStretch()
            .withLayout(
                HBoxBuilder()
                .withWidget(self.exportButton)
                .withStretch()
                .withWidget(ButtonBuilder("Cancel").onClick(self.reject))
            )
        )

        self._suggestPath()
        self.imageParam.sigParameterChanged.connect(lambda _: self._suggestPath())
        self.pathEdit.textChanged.connect(
            lambda text: self.exportButton.setEnabled(bool(text.strip()))
        )
        self.exportButton.setEnabled(bool(self.pathEdit.text().strip()))
        self.accepted.connect(self._export)

    def selectedImage(self) -> VardaRaster:
        return self.imageParam.get()

    def _suggestPath(self) -> None:
        image = self.selectedImage()
        if image is not None:
            self.pathEdit.setText(str(suggestedOutputPath(image)))

    def _browse(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export image as", self.pathEdit.text(), SAVE_FILE_FILTER
        )
        if path:
            self.pathEdit.setText(str(Path(path)))

    def _export(self) -> None:
        image = self.selectedImage()
        path = self.pathEdit.text().strip()
        progress = QProgressDialog(
            f"Writing {image.name} to {path}…", None, 0, 0, self.parentWidget()
        )
        progress.setWindowTitle("Export Image")
        progress.setMinimumDuration(0)

        job = _WriteJob(image, path)
        self._jobs.append(job)

        def onFinished(written: VardaRaster, writtenPath: str) -> None:
            progress.close()
            self._jobs.remove(job)
            self.sigExported.emit(written, writtenPath)

        def onFailed(error: Exception) -> None:
            progress.close()
            self._jobs.remove(job)
            QMessageBox.critical(
                self.parentWidget(),
                "Export failed",
                f"Could not write {path}:\n{error}",
            )

        job.signals.finished.connect(onFinished)
        job.signals.failed.connect(onFailed)
        pool = QThreadPool.globalInstance()
        assert pool is not None
        pool.start(job)
