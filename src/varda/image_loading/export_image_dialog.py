"""Export Image: pick an image and a destination, then write it in the background."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QWidget,
)

from varda.branding.loader import BusyDialog
from varda.common.entities import VardaRaster
from varda.common.parameter import ImageParameter
from varda.common.ui import ButtonBuilder, HBoxBuilder, VBoxBuilder
from varda.image_loading.raster_writer import (
    SAVE_FILE_FILTER,
    suggestedOutputPath,
    writeRaster,
)
from varda.common.parameter_widgets import parameterWidget
from varda.utilities.background import runInBackground


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

        self.imageParam = ImageParameter("Image", "The image to write")
        self.imageParam.setProvider(lambda: list(images))
        if image is not None:
            self.imageParam.set(image)

        self.pathEdit = QLineEdit()
        self.pathEdit.setPlaceholderText("ENVI (.img / .hdr) or GeoTIFF (.tif)")
        self.browseButton = ButtonBuilder("Browse…").onClick(self._browse)
        self.exportButton = ButtonBuilder("Export").onClick(self.accept)

        form = QFormLayout()
        form.addRow("Image", parameterWidget(self.imageParam))
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
        progress = BusyDialog(
            f"Writing {image.name} to {path}…",
            title="Export Image",
            parent=self.parentWidget(),
        )
        progress.show()

        def onFinished(_written: object) -> None:
            progress.close()
            self.sigExported.emit(image, path)

        def onFailed(error: Exception) -> None:
            progress.close()
            QMessageBox.critical(
                self.parentWidget(),
                "Export failed",
                f"Could not write {path}:\n{error}",
            )

        runInBackground(
            lambda: writeRaster(image, path),
            onFinished,
            onFailed,
            description=f"Writing {image.name} to {path}",
        )
