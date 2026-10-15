"""The Ames Stereo Pipeline entry in Optional Features: what was found and
where, a folder of the user's choosing, the pinned download, and removing
Varda's copy. Auto Align asks ``currentAsp`` for what to use."""

from __future__ import annotations

import platform
import threading
from pathlib import Path

from PyQt6.QtCore import QSettings, QStandardPaths, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from varda.common.ui import MutedLabel
from varda.mosaicking.backends.asp import (
    ASP_VERSION,
    AspError,
    AspInstall,
    downloadAsp,
    findAsp,
    releaseFor,
    removeDownload,
)
from varda.utilities.background import onMainThread, runInBackground

FOLDER_KEY = "asp/folder"
WINDOWS_NOTE = (
    "The Ames Stereo Pipeline has no Windows version (it runs in WSL, the "
    "Windows Subsystem for Linux). Varda's own alignment tools do everything "
    "Auto Align needs without it."
)

_cache: dict[str, AspInstall | None] = {}


def downloadRoot() -> Path:
    folder = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppLocalDataLocation
    )
    return Path(folder) / "runtimes" / "asp"


def chosenFolder() -> str:
    return str(QSettings().value(FOLDER_KEY, "") or "")


def currentAsp(redetect: bool = False) -> AspInstall | None:
    """The ASP to use (detected once per session unless asked again)."""
    if redetect or "asp" not in _cache:
        _cache["asp"] = findAsp(chosenFolder() or None, downloadRoot())
    return _cache["asp"]


class AspSection(QWidget):
    sigChanged = pyqtSignal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._cancel: threading.Event | None = None
        self.release = releaseFor()

        title = QLabel("Ames Stereo Pipeline")
        font = QFont(title.font())
        font.setBold(True)
        title.setFont(font)
        about = QLabel(
            "Optional: Auto Align in the Mosaic workspace can use ASP's "
            "image_align to match images. Varda uses an ASP you already have "
            f"(PATH, a conda environment named asp, ~/StereoPipeline-*), or "
            f"downloads ASP {ASP_VERSION} into its own folder."
        )
        about.setWordWrap(True)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setVisible(False)
        self.stepLabel = MutedLabel("")

        self.redetectButton = QPushButton("Re-detect")
        self.redetectButton.clicked.connect(lambda: self.refresh(redetect=True))
        self.chooseButton = QPushButton("Choose Folder…")
        self.chooseButton.setToolTip("An ASP folder (or its bin folder) to use")
        self.chooseButton.clicked.connect(self._choose)
        self.downloadButton = QPushButton(
            f"Download ASP {ASP_VERSION}"
            + (f" ({self.release.sizeMB:.0f} MB)" if self.release else "")
        )
        self.downloadButton.clicked.connect(self._download)
        self.cancelButton = QPushButton("Cancel Download")
        self.cancelButton.clicked.connect(self._cancelDownload)
        self.removeButton = QPushButton("Remove")
        self.removeButton.setToolTip("Delete the copy of ASP that Varda downloaded")
        self.removeButton.clicked.connect(self._remove)

        buttons = QHBoxLayout()
        for button in (
            self.redetectButton,
            self.chooseButton,
            self.downloadButton,
            self.cancelButton,
            self.removeButton,
        ):
            buttons.addWidget(button)
        buttons.addStretch()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(title)
        layout.addWidget(about)
        layout.addWidget(self.status)
        layout.addWidget(self.progress)
        layout.addWidget(self.stepLabel)
        layout.addLayout(buttons)
        self.refresh()

    def refresh(self, redetect: bool = False) -> None:
        install = currentAsp(redetect)
        busy = self._cancel is not None
        windows = platform.system() == "Windows"
        if windows:
            self.status.setText(WINDOWS_NOTE)
        elif install is None:
            self.status.setText("Not found.")
        else:
            self.status.setText(
                f"ASP {install.version} found ({install.source}):\n{install.bin}"
            )
        self.downloadButton.setVisible(self.release is not None and not windows)
        self.downloadButton.setEnabled(not busy and install is None)
        self.cancelButton.setVisible(busy)
        self.removeButton.setVisible(
            install is not None and install.source == "Varda download"
        )
        self.chooseButton.setEnabled(not busy and not windows)
        self.redetectButton.setEnabled(not busy)
        if redetect:
            self.sigChanged.emit()

    def _choose(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose the ASP Folder")
        if not folder:
            return
        found = findAsp(folder, env={"PATH": ""}, home=Path(folder) / "none")
        if found is None:
            QMessageBox.warning(
                self,
                "Ames Stereo Pipeline",
                f"There's no working image_align in {folder} or its bin folder.",
            )
            return
        QSettings().setValue(FOLDER_KEY, folder)
        self.refresh(redetect=True)

    def _download(self) -> None:
        if self.release is None:
            return
        self._cancel = threading.Event()
        cancel, release = self._cancel, self.release
        self.progress.setValue(0)
        self.progress.setVisible(True)
        progress = onMainThread(self._showProgress)
        runInBackground(
            lambda: downloadAsp(release, downloadRoot(), progress, cancel),
            self._downloaded,
            self._downloadFailed,
            description="Downloading the Ames Stereo Pipeline",
        )
        self.refresh()

    def _showProgress(self, fraction: float, message: str) -> None:
        self.progress.setValue(int(100 * fraction))
        self.stepLabel.setText(message[:1].upper() + message[1:] + "…")

    def _downloaded(self, install: AspInstall) -> None:
        self._cancel = None
        self.progress.setVisible(False)
        self.stepLabel.setText(f"ASP {install.version} is ready.")
        self.refresh(redetect=True)

    def _downloadFailed(self, error: Exception) -> None:
        self._cancel = None
        self.progress.setVisible(False)
        self.stepLabel.setText(str(error))
        self.refresh()

    def _cancelDownload(self) -> None:
        if self._cancel is not None:
            self._cancel.set()

    def cancelRunning(self) -> None:
        """Stop a download (when the window closes)."""
        self._cancelDownload()

    def _remove(self) -> None:
        install = currentAsp()
        if install is None:
            return
        try:
            removeDownload(install)
        except AspError as error:
            self.stepLabel.setText(str(error))
        self.refresh(redetect=True)
