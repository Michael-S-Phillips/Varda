"""Pick the images for a new Mosaic workspace."""

from __future__ import annotations

from collections.abc import MutableSequence

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QVBoxLayout,
)

from varda.common.entities import VardaRaster
from varda.mosaicking.model import MosaicError
from varda.workspaces.mosaic.mosaic_workspace import MosaicWorkspace


class NewMosaicDialog(QDialog):
    sigCreateWorkspace = pyqtSignal(object)

    def __init__(self, images: MutableSequence[VardaRaster], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Mosaic Workspace")
        self.images = images
        intro = QLabel(
            "Choose two or more overlapping images with the same bands and map "
            "projection. The first is on top where they overlap; you can reorder them."
        )
        intro.setWordWrap(True)
        self.list = QListWidget()
        for image in images:
            item = QListWidgetItem(image.name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.list.addItem(item)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Open
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._create)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addWidget(self.list, 1)
        layout.addWidget(buttons)

    def chosen(self) -> list[VardaRaster]:
        return [
            image
            for row, image in enumerate(self.images)
            if self.list.item(row).checkState() == Qt.CheckState.Checked
        ]

    def _create(self) -> None:
        try:
            workspace = MosaicWorkspace(self.chosen(), self.images)
        except MosaicError as error:
            QMessageBox.warning(self, "New Mosaic Workspace", str(error))
            return
        self.sigCreateWorkspace.emit(workspace)
        self.accept()

    def connectOnAccept(self, callback):
        self.sigCreateWorkspace.connect(callback)
        return self
