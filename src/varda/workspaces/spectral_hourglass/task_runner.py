"""Runs one hourglass step at a time in the background, reporting progress."""

from __future__ import annotations

import logging
from collections.abc import Callable

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, str], None]
Task = Callable[[ProgressCallback], object]


class _Signals(QObject):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(object)
    failed = pyqtSignal(object)


class _Job(QRunnable):
    def __init__(self, task: Task) -> None:
        super().__init__()
        self.task = task
        self.signals = _Signals()

    def run(self) -> None:
        try:
            result = self.task(self.signals.progress.emit)
        except Exception as error:  # shown to the user by the workspace
            logger.exception("Spectral hourglass step failed")
            self.signals.failed.emit(error)
            return
        self.signals.finished.emit(result)


class TaskRunner(QObject):
    """One task at a time. ``synchronous`` runs tasks inline (for tests)."""

    sigBusyChanged = pyqtSignal(bool)
    sigProgress = pyqtSignal(int, str)  # percent, "<label>: <message>"
    sigFailed = pyqtSignal(str, object)  # label, exception

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.synchronous = False
        self._job: _Job | None = None

    @property
    def busy(self) -> bool:
        return self._job is not None

    def run(self, label: str, task: Task, onDone: Callable[[object], None]) -> None:
        if self.busy:
            return
        if self.synchronous:
            self.sigBusyChanged.emit(True)
            try:
                result = task(lambda p, m: self.sigProgress.emit(p, f"{label}: {m}"))
            except Exception as error:
                self.sigBusyChanged.emit(False)
                self.sigFailed.emit(label, error)
                return
            self.sigBusyChanged.emit(False)
            onDone(result)
            return
        job = _Job(task)
        self._job = job

        def finished(result: object) -> None:
            self._job = None
            self.sigBusyChanged.emit(False)
            onDone(result)

        def failed(error: object) -> None:
            self._job = None
            self.sigBusyChanged.emit(False)
            self.sigFailed.emit(label, error)

        job.signals.progress.connect(
            lambda p, m: self.sigProgress.emit(p, f"{label}: {m}")
        )
        job.signals.finished.connect(finished)
        job.signals.failed.connect(failed)
        self.sigBusyChanged.emit(True)
        pool = QThreadPool.globalInstance()
        assert pool is not None
        pool.start(job)
