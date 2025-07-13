"""
task_queue_api.py

Simple task queue and progress API for PyQt6 applications.
"""

import logging

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal
from typing import Callable, Any, Dict

logger = logging.getLogger(__name__)


class TaskSignals(QObject):
    """
    Signals available from a running task:
      - taskStarted(taskId: str)
      - progressUpdated(taskId: str, percent: int)
      - taskFinished(taskId: str)
      - taskError(taskId: str, exception: Exception)
      - taskCancelled(taskId: str)
    """

    taskStarted = pyqtSignal(str)
    progressUpdated = pyqtSignal(str, int)
    taskFinished = pyqtSignal(str)
    taskError = pyqtSignal(str, Exception)
    taskCancelled = pyqtSignal(str)


class Task(QRunnable):
    """
    Wrapper around a callable to run in a QThreadPool with progress reporting.
    Worker functions should check `task.isCancelled` periodically.
    """

    def __init__(self, taskId: str, func: Callable[..., Any], *args, **kwargs):
        super().__init__()
        self.taskId = taskId
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.signals = TaskSignals()
        self.isCancelled = False
        self.isFinished = False

    def run(self):
        # If cancelled before start, emit cancel and finish immediately
        if self.isCancelled:
            self._finish(cancelled=True)
            return

        try:
            self.signals.taskStarted.emit(self.taskId)
            result = self.func(self.progressCallback, *self.args, **self.kwargs)
            self._finish()
            return result
        except Exception as e:
            logger.error(f"Error in task {self.taskId}: {e}", exc_info=True)
            self.signals.taskError.emit(self.taskId, e)
            self._finish()

    def progressCallback(self, percent: int):
        """
        Called by the worker function to update progress (0-100).
        """
        if not self.isCancelled:
            self.signals.progressUpdated.emit(self.taskId, percent)

    def cancel(self):
        """
        Request cancellation; worker functions should check `isCancelled`.
        Emits a cancel signal and marks as finished in queue.
        """
        if not self.isFinished:
            self.isCancelled = True
            self.signals.taskCancelled.emit(self.taskId)

    def _finish(self, cancelled: bool = False):
        """
        Internal: emit finished and mark task as done.
        """
        if not self.isFinished:
            self.signals.taskFinished.emit(self.taskId)
            self.isFinished = True


class TaskQueue:
    """
    Manages submission and cancellation of background tasks.
    """

    def __init__(self, maxWorkers: int = 4):
        self.threadPool = QThreadPool.globalInstance()
        self.threadPool.setMaxThreadCount(maxWorkers)
        self.tasks: Dict[str, Task] = {}

    def submitTask(
        self, taskId: str, func: Callable[..., Any], *args, **kwargs
    ) -> TaskSignals:
        """
        Schedule a new task. Returns the TaskSignals to connect UI handlers.
        """
        task = Task(taskId, func, *args, **kwargs)
        self.tasks[taskId] = task
        self.threadPool.start(task)
        return task.signals

    def cancelTask(self, taskId: str) -> None:
        """
        Signal cancellation to the running task and remove from queue.
        """
        task = self.tasks.get(taskId)
        if task:
            task.cancel()
            # drop reference; completion signals may still arrive
            del self.tasks[taskId]

    def clearTasks(self) -> None:
        """
        Removes references to finished tasks.
        """
        self.tasks = {tid: t for tid, t in self.tasks.items() if not t.isFinished}
