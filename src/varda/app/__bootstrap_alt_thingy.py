"""
Example of how to update the application bootstrap to use the new _test_project_module_thing feature.

This is an example file showing how to modify the existing bootstrap.py to use
the new _test_project_module_thing feature instead of the old ProjectContext.
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
from varda.app.image import ImageLoadingService
from varda._test_project_module_thing import bootstrap as workspace_bootstrap
from varda.gui.maingui import (
    MainGUI,
)  # This would need to be updated to use WorkspaceService


logger = logging.getLogger(__name__)


q_app: QApplication = None


def initVarda(startGui=True) -> None:
    """
    Initialize and start the Varda application.
    """
    global q_app

    q_app = initPyQtAndLogging()

    # Any configuration settings that need to be applied before starting the program goes here
    setConfigurations()

    # Initialize the core components
    initializeServices()

    # Let plugins run their startup code -- can only be done after the app api has been set up
    varda.app.pm.hook.onLoad()

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
    """Setup logging. Logs will be saved in the user's local appdata folder."""
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
    """Initialize any configuration settings for Varda."""
    pg.setConfigOptions(imageAxisOrder="row-major")


def initializeServices() -> None:
    """Initialize all services and register them in the registry."""
    # Initialize the registry
    from varda.infra.registry import VardaRegistries

    registry = VardaRegistries()
    varda.app.registry = registry

    # Initialize the plugin manager
    from varda.infra.plugins.plugin_manager import VardaPluginManager

    pm = VardaPluginManager()
    varda.app.pm = pm

    # Initialize the image loading service
    image_loading_service = ImageLoadingService()
    registry.imageLoaders.register("image_loading_service", image_loading_service)

    # Initialize the _test_project_module_thing service
    workspace_bootstrap.register_workspace_service(registry, image_loading_service)

    # Make the _test_project_module_thing service available globally through varda.app.proj
    # This maintains backward compatibility with code that uses varda.app.proj
    varda.app.proj = registry.get("workspace_service")


def startGUI() -> NoReturn:
    """Enter the GUI event loop. This function never returns."""
    global q_app

    if q_app is None:
        raise RuntimeError("Varda must be initialized before starting the GUI.")

    # Get the _test_project_module_thing service from the registry
    workspace_service = varda.app.registry.get("workspace_service")

    # Create the main GUI with the _test_project_module_thing service
    gui = MainGUI(workspace_service)
    gui.showMaximized()
    logger.debug("starting the GUI event loop...")
    exitCode = q_app.exec()
    logger.info("Application exiting, performing cleanup...")
    sys.exit(exitCode)
