import logging
import sys
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import QStandardPaths
from PyQt6.QtWidgets import QApplication


def info(msg, *args, **kwargs):
    logging.getLogger(_getCallerName()).info(msg, *args, **kwargs)


def debug(msg, *args, **kwargs):
    logging.getLogger(_getCallerName()).debug(msg, *args, **kwargs)


def warning(msg, *args, **kwargs):
    logging.getLogger(_getCallerName()).warning(msg, *args, **kwargs)


def error(msg, *args, **kwargs):
    logging.getLogger(_getCallerName()).error(msg, *args, **kwargs)


def critical(msg, *args, **kwargs):
    logging.getLogger(_getCallerName()).critical(msg, *args, **kwargs)


def _getCallerName(depth: int = 1) -> str:
    """The calling module's logger name. The packaged app's entry script runs
    as ``__main__``; its messages belong under ``varda`` too."""
    frame = sys._getframe(depth + 1)
    name = frame.f_globals.get("__name__") or VARDA_LOGGER
    return "varda.main" if name == "__main__" else name


### Initialize Logging -- Logs stored in user's local appdata folder ###
# Nothing is configured at import: importing Varda (e.g. in a notebook or the
# tests) leaves the host's logging alone. The app calls _initializeFullLogging.

VARDA_LOGGER = "varda"
LOG_FORMAT = "%(levelname)s:%(name)s:%(message)s"


def _initializeFullLogging(logFolder: Path | None = None):
    """This can be called by the main application to initialize full logging.
    ``logFolder`` defaults to the Logs folder in the user's app-data location."""
    if logFolder is None:
        assert QApplication.instance() is not None, "QApplication must be initialized"
        logFolder = (
            Path(
                QStandardPaths.writableLocation(
                    QStandardPaths.StandardLocation.AppLocalDataLocation
                )
            )
            / "Logs"
        )
    logFolder.mkdir(parents=True, exist_ok=True)
    # Get existing log files and remove the oldest ones if there are too many
    maxLogs = 10
    log_files = sorted(logFolder.glob("Varda.*.log"), key=lambda f: f.stat().st_mtime)
    while len(log_files) >= maxLogs:
        log_files[0].unlink()  # Delete the oldest log file
        log_files.pop(0)
    # compute name for new log file
    logTime = datetime.now().strftime("%Y-%m-%d_%I-%M-%S-%p")
    logName = logFolder / f"Varda.{logTime}.log"
    # Varda's own messages in detail; every other library only its warnings
    # (the root logger), both to the log file and the console.
    formatter = logging.Formatter(LOG_FORMAT)
    handlers: list[logging.Handler] = [
        logging.FileHandler(logName),
        logging.StreamHandler(sys.stdout),
    ]
    for handler in handlers:
        handler.setFormatter(formatter)
    logging.basicConfig(level=logging.WARNING, handlers=handlers, force=True)
    logging.getLogger(VARDA_LOGGER).setLevel(logging.DEBUG)
    debug("logging fully initialized, output file found in local appdata folder")
