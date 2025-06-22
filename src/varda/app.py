"""
Composition Root for Varda

This module initializes all the core components of Varda right away, and then starts the GUI.

These core components are then accessible under the varda namespace, e.g. `varda.proj`, `varda.widgetRegistry`, etc.
"""

# standard library
from datetime import datetime
import importlib
import logging
from pathlib import Path
import sys

# third party imports
from PyQt6.QtCore import QStandardPaths
from PyQt6.QtWidgets import QApplication
import pyqtgraph as pg
from pluggy import PluginManager

# local imports
import varda
from varda.core.data import ProjectContext
from varda.gui.maingui import MainGUI
from varda.plugins.plugin_manager import VardaPluginManager
from varda.registries import WidgetRegistry, ImageLoaderRegistry


logger = logging.getLogger(__name__)


class VardaSessionContext:
    """
    Context for the current Varda session.
    Includes the project context, registry, and plugin manager.
    """

    def __init__(self):
        self.proj = ProjectContext()
        self.registry = VardaRegistry()
        self.pm = VardaPluginManager()


class VardaRegistry:
    """Registry to store dynamically loaded widgets and image loaders. (e.g. plugins)"""

    def __init__(self):
        self.widgets = WidgetRegistry()
        self.imageLoaders = ImageLoaderRegistry()


sessionContext = VardaSessionContext()

q_app = QApplication(sys.argv)


def initVarda():
    """
    Initialize and start the Varda application.
    """
    global sessionContext, q_app

    # Initialize the application
    q_app = QApplication(sys.argv)
    q_app.setApplicationName("Varda")
    q_app.setOrganizationName("Varda")

    # Initialize logging
    _initLogging()
    logger.debug("Initializing VardaApp")

    # Any configuration settings that need to be applied before starting the program goes here
    pg.setConfigOptions(imageAxisOrder="row-major")

    # initialize the session context
    sessionContext = VardaSessionContext()

    # Now that initialization is done, launch the GUI
    startGUI()


def startGUI():
    """Enter the GUI event loop."""
    global sessionContext, q_app
    gui = MainGUI(sessionContext.proj)
    gui.showMaximized()
    logger.debug("starting the application event loop")
    exitCode = q_app.exec()
    logging.info("Application exiting, performing cleanup...")
    sys.exit(exitCode)


def _initLogging():
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
