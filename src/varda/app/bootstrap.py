"""
Composition Root for Varda

This module initializes all the core components of Varda right away, and then starts the GUI.

These core components are then accessible via the "varda.app" namespace
"""

# standard library
from datetime import datetime
import logging
from pathlib import Path
import sys
from typing import NoReturn

# third party imports
from PyQt6.QtCore import QStandardPaths
from PyQt6.QtWidgets import QApplication
import pyqtgraph as pg

# local imports
import varda.app
from varda.app.varda_session_context import VardaSessionContext
from varda.gui.maingui import MainGUI


logger = logging.getLogger(__name__)


sessionContext: VardaSessionContext = VardaSessionContext()
q_app: QApplication = None


def initVarda(startGui=True) -> None:
    """
    Initialize and start the Varda application.
    """
    global sessionContext, q_app

    q_app = initPyQtAndLogging()

    # Any configuration settings that need to be applied before starting the program goes here
    setConfigurations()

    # Initialize the core components
    sessionContext = VardaSessionContext()

    varda.app.proj = sessionContext.proj
    varda.app.registry = sessionContext.registry
    varda.app.pm = sessionContext.pm

    # let plugins run their startup code -- can only be done after the app api has been set up
    sessionContext.pm.hook.onLoad()

    # start gui
    logger.info("Varda initialized successfully!")
    if startGui:
        startGUI()


def initPyQtAndLogging() -> QApplication:
    """Initialize the QApplication and logging for Varda.

    They go together because logging relies on PyQt to determine where to store logs.
    """
    global q_app
    # Initialize the QApplication
    q_app = QApplication(sys.argv)
    q_app.setApplicationName("Varda")
    q_app.setOrganizationName("Varda")

    # Initialize logging
    initLogging()
    logger.debug("QApplication and logging initialized")
    return q_app


def initLogging() -> None:
    """Setup logging. Logs will be saved in the user's local appdata folder.
    # TODO: Add a GUI button to open the log folder.

    Usage: create a logger object in any file and use it to log messages, e.g.

      import logging
      logger = logging.getLogger(__name__)
      logger.debug("This is a debug message")
      logger.info("This is an info message")
      logger.warning("This is a warning message")
      logger.error("This is an error message")
    """
    if q_app is None:
        raise RuntimeError("QApplication must be initialized before logging.")

    logFolder = (
        Path(
            QStandardPaths.writableLocation(
                QStandardPaths.StandardLocation.AppLocalDataLocation
            )
        )
        / "Logs"
    )
    logFolder.mkdir(parents=True, exist_ok=True)

    # Limit the number of log files
    maxLogs = 10
    log_files = sorted(logFolder.glob("Varda.*.log"), key=lambda f: f.stat().st_mtime)
    while len(log_files) >= maxLogs:
        log_files[0].unlink()  # Delete the oldest log file
        log_files.pop(0)

    logTime = datetime.now().strftime("%Y-%m-%d_%I-%M-%S-%p")
    logName = logFolder / f"Varda.{logTime}.log"

    logging.basicConfig(
        level=logging.DEBUG,
        handlers=[logging.FileHandler(logName), logging.StreamHandler(sys.stdout)],
    )


def setConfigurations() -> None:
    """Initialize any configuration settings for Varda.

    This function can be used to set up default configurations, load user preferences,
    or apply any other necessary settings before starting the application.
    """
    pg.setConfigOptions(imageAxisOrder="row-major", background="w")


def startGUI() -> NoReturn:
    """Enter the GUI event loop. This function never returns."""
    global sessionContext, q_app

    if sessionContext is None or q_app is None:
        raise RuntimeError("Varda must be initialized before starting the GUI.")

    gui = MainGUI(sessionContext.proj)
    gui.showMaximized()
    logger.debug("starting the GUI event loop...")
    exitCode = q_app.exec()
    logger.info("Application exiting, performing cleanup...")
    sys.exit(exitCode)
