"""
Main entry point for the application.
This file is responsible for setting up logging and starting the GUI.
"""

# standard library
from pathlib import Path
from datetime import datetime
import logging
import sys
import os
import atexit
import importlib
import importlib.util

# third party imports
import pyqtgraph as pg
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QStandardPaths
from pluggy import PluginManager
from appdirs import user_log_dir

# local imports
from varda.gui import maingui
from varda.core.data import ProjectContext
import varda


def initPluginManager():
    """
    Initialize the plugin manager and load plugins.

    Plugins installed with pip/conda will be automatically detected.
    Plugins can also be placed inside the user_plugins folder,
    this is easier for quick testing or writing plugins you don't intend to publish.
    """
    pm = PluginManager("varda")
    pm.add_hookspecs(varda.api._hookspecs)
    # load plugins from entrypoints
    pm.load_setuptools_entrypoints("varda.plugins")

    # load plugins from local "user_plugins" package
    # plugins can either be standalone py files, or a package
    currPath = Path(__file__).resolve().parent
    pluginFolder = currPath / "user_plugins"
    pluginExamplesFolder = pluginFolder / "examples"
    registerPluginsInFolder(pm, pluginFolder)
    return pm


def registerPluginsInFolder(pm, pluginFolder):
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
        mod = importlib.import_module(f"varda.user_plugins.{moduleName}")
        pm.register(mod)


def initLogging():
    """Setup logging. Logs will be saved in the "logs" directory. with a unique timestamp

    Usage: create a logger object in any file and use it to log messages, e.g.

      import logging
      logger = logging.getLogger(__name__)
      logger.debug("This is a debug message")
      logger.info("This is an info message")
      logger.warning("This is a warning message")
      logger.error("This is an error message")
    """
    logFolder = user_log_dir("Varda", False)
    os.makedirs(logFolder, exist_ok=True)

    # Limit the number of log files
    max_logs = 10
    log_files = sorted(Path(logFolder).glob("Varda.*.log"), key=os.path.getmtime)
    while len(log_files) >= max_logs:
        log_files[0].unlink()  # Delete the oldest log file
        log_files.pop(0)

    logTime = datetime.now().strftime("%Y-%m-%d_%I-%M-%S-%p")
    logName = Path(f"{logFolder}/Varda.{logTime}.log")
    logging.basicConfig(
        level=logging.DEBUG,
        handlers=[logging.FileHandler(logName), logging.StreamHandler(sys.stdout)],
    )


def setupConfig():
    """Any configuration settings that need to be applied before starting the program goes here"""
    pg.setConfigOptions(imageAxisOrder="row-major")


def cleanup():
    """Clean up resources before application exit."""
    logging.info("Application exiting, performing cleanup...")
    # Force any remaining QApplication instances to quit
    app = QApplication.instance()
    if app:
        app.quit()


def main():
    initLogging()

    # Register cleanup function to be called on exit
    atexit.register(cleanup)

    pm = initPluginManager()
    print("Plugin manager initialized")
    pm.hook.onLoad()
    setupConfig()
    proj = ProjectContext()
    varda.api.proj = proj
    try:
        maingui.startGui(proj)
    except Exception as e:
        logging.error(f"Error in main application: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
