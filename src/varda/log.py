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


def _getCallerName(depth: int = 1) -> str | None:

    frame = sys._getframe(depth + 1)
    return frame.f_globals.get("__name__")


### Initialize Logging -- Logs stored in user's local appdata folder ###


def _initializeFullLogging():
    """This can be called by the main application to initialize full logging."""
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
    logging.basicConfig(
        level=logging.DEBUG,
        handlers=[logging.FileHandler(logName), logging.StreamHandler(sys.stdout)],
    )
    debug("logging fully initialized, output file found in local appdata folder")


# By default, the logger only uses stdout
logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler(sys.stdout)])
