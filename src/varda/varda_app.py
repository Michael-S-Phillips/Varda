# standard library
import logging
import sys
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass

# third party imports
from PyQt6.QtCore import QStandardPaths
from PyQt6.QtWidgets import QApplication
import pyqtgraph as pg

# local imports
import varda
from varda.core.data import ProjectContext
from varda.plugins.plugin_manager import initPluginManager
from varda.gui.maingui import MainGUI
from varda.registries import WidgetRegistry, ImageLoaderRegistry

logger = logging.getLogger(__name__)


class VardaApp:
    """
    VardaApp is the main application controller. It initializes everything needed, And starts the GUI.
    """

    def __init__(self):
        """Initialize the Varda application.

        Note that this does not start the GUI. To do that, you need to call `run()` after. Maybe useful for testing.
        """
        # Initialize the application
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("Varda")
        self.app.setOrganizationName("Varda")

        # Initialize logging
        self._initLogging()
        logger.debug("Initializing VardaApp")

        # Any configuration settings that need to be applied before starting the program goes here
        pg.setConfigOptions(imageAxisOrder="row-major")

        # Initialize the project context
        self.proj = ProjectContext()

        # initialize the plugin manager
        self.pm = initPluginManager()

        # start GUI
        self.gui = MainGUI(self.proj)
        self.gui.showMaximized()

        self.gui.

    def run(self):
        """Run the Varda application."""
        logger.debug("starting the application event loop")
        exitCode = self.app.exec()
        logging.info("Application exiting, performing cleanup...")
        sys.exit(exitCode)

    def _initLogging(self):
        """Setup logging. Logs will be saved in the "logs" directory. with a unique timestamp

        Usage: create a logger object in any file and use it to log messages, e.g.

          import logging
          logger = logging.getLogger(__name__)
          logger.debug("This is a debug message")
          logger.info("This is an info message")
          logger.warning("This is a warning message")
          logger.error("This is an error message")
        """
        logFolder = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)) / "Logs"
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

@dataclass
class VardaApplicationContext:
    """
    A context manager for the Varda application. This is useful for testing or when you need to ensure that the application
    is properly initialized and cleaned up.
    """
    proj: ProjectContext
    widgetRegistry: WidgetRegistry
    imageLoaderRegistry: ImageLoaderRegistry
