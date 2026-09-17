"""Autosave the session every few minutes and on quit, so a crash costs at
most a few minutes of work. File > Restore Last Session reopens it."""

from __future__ import annotations

import logging
from pathlib import Path

from PyQt6.QtCore import QObject, QStandardPaths, QTimer
from PyQt6.QtWidgets import QApplication

from varda.common.di_types import ProjectImages
from varda.session import SessionCapture, captureSession, writeSession

logger = logging.getLogger(__name__)

AUTOSAVE_FILE_NAME = "autosave.varda"
DEFAULT_INTERVAL_MS = 3 * 60 * 1000


def defaultAutosavePath() -> Path:
    """The autosave file in the user's app-data folder (next to the logs)."""
    folder = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppLocalDataLocation
    )
    return Path(folder) / AUTOSAVE_FILE_NAME


class SessionAutosaver(QObject):
    def __init__(
        self,
        images: ProjectImages,
        mainGui,
        *,
        path: Path | None = None,
        intervalMs: int = DEFAULT_INTERVAL_MS,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._images = images
        self._mainGui = mainGui
        self.path = Path(path) if path is not None else defaultAutosavePath()

        self._timer = QTimer(self)
        self._timer.setInterval(intervalMs)
        self._timer.timeout.connect(self.saveNow)
        self._timer.start()
        app = QApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.saveNow)

    def saveNow(self) -> SessionCapture | None:
        """Write the session, unless nothing file-backed is open: an empty
        autosave would only destroy a useful earlier one."""
        capture = captureSession(list(self._images), self._mainGui.childWindows)
        if not capture.state.images:
            return None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        writeSession(capture.state, self.path)
        logger.debug("Session autosaved to %s", self.path)
        return capture
