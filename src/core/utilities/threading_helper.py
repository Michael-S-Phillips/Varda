# standard library
import logging

# third party imports
from PyQt6 import QtCore


logger = logging.getLogger(__name__)


threadpool = QtCore.QThreadPool()


def dispatchThreadProcess(onComplete, process, *args, **kwargs):
    """General purpose method to dispatch a process to a thread.

    Args:
        onComplete (callable): The function to call when the process is complete.
        process (callable): The function to run in the background thread.
        *args: Variable length argument list for the process function.
        **kwargs: keyword arguments for the process function.
    """
    worker = BackgroundWorker(process, *args, **kwargs)
    worker.signals.result.connect(onComplete)
    threadpool.start(worker)


class BackgroundWorker(QtCore.QRunnable):
    """A basic setup to run functions on a separate thread."""

    class Signals(QtCore.QObject):
        """QRunnable cannot define pyqtSignals because it doesn't inherit from QObject
        So we create this inner class to define signals.
        """

        finished = QtCore.pyqtSignal()
        result = QtCore.pyqtSignal(object)

    def __init__(self, fn, *args, **kwargs):
        """Initializes the worker.

        Args:
            fn (callable): The function to run on a separate thread.
            *args: Variable length argument list for the function.
            **kwargs: keyword arguments for the function.
        """
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self.signals = self.Signals()

    @QtCore.pyqtSlot()
    def run(self):
        """Runs the function on a separate thread and emits the result signal."""
        logger.info(
            "run(): calling function " + self._fn.__name__ + " on thread.\n"
            "  args: " + str(*self._args) + "\n"
            "  kwargs: " + str(**self._kwargs)
        )

        result = self._fn(*self._args, **self._kwargs)
        self.signals.result.emit(result)
