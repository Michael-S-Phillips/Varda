import logging

logger = logging.getLogger(__name__)

from PyQt6 import QtCore

threadpool = QtCore.QThreadPool()


def dispatchThreadProcess(onComplete, process, *args, **kwargs):
    """
    General purpose method to dispatch a process to a thread
    """
    # initialize BackgroundWorker
    worker = BackgroundWorker(process, *args, **kwargs)
    # connect signals
    worker.signals.result.connect(onComplete)
    # dispatch thread
    threadpool.start(worker)


class BackgroundWorker(QtCore.QRunnable):
    """
    A basic setup to run functions on a separate thread.
    """

    class Signals(QtCore.QObject):
        """
        QRunnable cannot define pyqtSignals because it doesn't inherit from QObject
        So we create this inner class to define signals
        """
        finished = QtCore.pyqtSignal()
        result = QtCore.pyqtSignal(object)

    def __init__(self, fn, *args, **kwargs):
        """
        Initializes the worker with the function it is to execute when being run
        @param fn: The function we want to run on a seperate thread
        @param obj: The object that the function belongs to
        @param args: any necessary function arguments
        @param kwargs: any necessary function keyword arguments
        """
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs
        self.signals = self.Signals()

    @QtCore.pyqtSlot()
    def run(self):
        logger.info(
            "run(): calling function " + self._fn.__name__ +
            " on thread.\n"
            "  args: " + str(*self._args) + "\n"
            "  kwargs: " + str(**self._kwargs)
        )

        result = self._fn(*self._args, **self._kwargs)
        self.signals.result.emit(result)
