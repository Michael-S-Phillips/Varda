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


class VardaRegistry:
    def __init__(self):
        self.widgets = WidgetRegistry()
        self.imageLoaders = ImageLoaderRegistry()


proj = ProjectContext()
registry = VardaRegistry()
pm = VardaPluginManager()


def initVarda():
    """
    Initialize and start the Varda application.
    """
    global proj, registry, pm

    # Initialize the application
    app = QApplication(sys.argv)
    app.setApplicationName("Varda")
    app.setOrganizationName("Varda")

    # Initialize logging
    _initLogging()
    logger.debug("Initializing VardaApp")

    # Any configuration settings that need to be applied before starting the program goes here
    pg.setConfigOptions(imageAxisOrder="row-major")

    # initialize project context
    proj = ProjectContext()

    # initialize registry
    registry = VardaRegistry()

    # Initialize the plugin manager
    pm = _initPluginManager()

    # Now that initialization is done, launch the GUI
    startGUI()


def startGUI():
    """Enter the GUI event loop."""
    global app
    gui = MainGUI(proj)
    gui.showMaximized()
    logger.debug("starting the application event loop")
    exitCode = app.exec()
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


def _initPluginManager():
    """
    Initialize the plugin manager and load plugins.

    Plugins installed with pip/conda will be automatically detected.
    Plugins can also be placed inside the user_plugins folder,
    this is easier for quick testing or writing plugins you don't intend to publish.
    """
    pm = PluginManager("varda")
    pm.add_hookspecs(varda.plugins._hookspecs)
    # load plugins from entrypoints
    pm.load_setuptools_entrypoints("varda.plugins")

    # load plugins from local "user_plugins" package
    # plugins can either be standalone .py files, or an installed package
    currPath = Path(__file__).resolve().parent
    pluginFolder = currPath / "plugins/user_plugins"
    _registerPluginsInFolder(pm, pluginFolder)
    return pm


def _registerPluginsInFolder(pm, pluginFolder):
    for name in pluginFolder.iterdir():
        name = name.name
        path = pluginFolder.joinpath(name)
        if name.endswith(".py"):
            # plugin is a standalone file
            moduleName = name[:-3]
        elif path.is_dir() and path.joinpath("__init__.py").is_file():
            # plugin is a package
            moduleName = name
        else:
            continue
        mod = importlib.import_module(f"varda.plugins.user_plugins.{moduleName}")
        pm.register(mod)
