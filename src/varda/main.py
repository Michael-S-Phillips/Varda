"""
Entrypoint for Varda
This module initializes all the core components of Varda right away, and then starts the GUI.
"""

from varda.gui.widgets import VardaMenuBar, StatusBar
from varda.newmaingui import VardaMainWindow
from varda.varda_application import VardaApplication


# standard library
from datetime import datetime
import logging
from pathlib import Path
import sys
from typing import NoReturn

# third party imports
from PyQt6.QtCore import QStandardPaths
from PyQt6.QtGui import QPixmap, QAction
from PyQt6.QtWidgets import QApplication, QSplashScreen
import pyqtgraph as pg

# local imports
import varda
from varda.app.varda_session_context import VardaSessionContext
from varda.gui.maingui import MainGUI

logger = logging.getLogger(__name__)

q_app: QApplication = None

splash: QSplashScreen = None


def quitApp():
    q_app.quit()


# temp thing for now. Eventually going to make an action registry / manager class
actions = []


def createAction(name: str, callback, shortcut=None):
    action = QAction(name)
    # we wrap the calback in a lambda to avoid passing the "checked" bool argument that the triggered signal emits
    action.triggered.connect(lambda: callback())
    if shortcut:
        action.setShortcut(shortcut)
    return action


def initMenuBar():
    ### Initialize Actions ###
    importImageAction = createAction(
        "Import Image", varda.app.proj.loadNewImage, "Ctrl+N"
    )
    saveProjectAction = createAction("Save Project", varda.app.proj.saveProject, "Ctrl+S")
    openProjectAction = createAction("Open Project", varda.app.proj.loadProject, "Ctrl+O")
    exitAppAction = createAction("Exit", quitApp)
    dumpProjectDataAction = createAction(
        "Dump Project Data",
        lambda: varda.utilities.debug.ProjectContextDataTable(varda.app.proj, None),
    )
    actions.append(importImageAction)
    actions.append(saveProjectAction)
    actions.append(openProjectAction)
    actions.append(exitAppAction)
    actions.append(dumpProjectDataAction)

    ### Initialize MenuBar ###
    menuBar = VardaMenuBar()
    menuBar.registerAction("File", importImageAction)
    menuBar.registerAction("File", saveProjectAction)
    menuBar.registerAction("File", openProjectAction)
    menuBar.registerAction("File", exitAppAction)
    menuBar.registerAction("Debug", dumpProjectDataAction)
    return menuBar


def startGUI() -> NoReturn:
    """Enter the GUI event loop. This function never returns."""
    global q_app, splash

    if q_app is None:
        raise RuntimeError("Everything must be initialized before starting the GUI.")

    gui = MainGUI(varda.app.proj, initMenuBar(), StatusBar(varda.app.proj))

    gui.showMaximized()
    logger.debug("starting the GUI event loop...")
    splash.finish(gui)
    exitCode = q_app.exec()
    logger.info("Application exiting, performing cleanup...")
    sys.exit(exitCode)


def setConfigurations() -> None:
    """Initialize any configuration settings for Varda.

    This function can be used to set up default configurations, load user preferences,
    or apply any other necessary settings before starting the application.
    """
    pg.setConfigOptions(imageAxisOrder="row-major")


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

    OR you can use the varda.log convenience module:

        import varda
        varda.log.debug("This is a debug message")
        varda.log.info("This is an info message")
        varda.log.warning("This is a warning message")
        varda.log.error("This is an error message")
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


def initPyqtApp() -> QApplication:
    """Initialize the QApplication and logging for Varda.

    They go together because logging relies on PyQt to determine where to store logs.
    """
    global q_app, splash
    # Initialize the QApplication
    q_app = QApplication(sys.argv)
    q_app.setApplicationName("Varda")
    q_app.setOrganizationName("Varda")
    splash = QSplashScreen(QPixmap("resources/logo.svg"))
    splash.show()
    q_app.processEvents()
    return q_app


def initVarda() -> None:
    """
    Initialize and start the Varda application.
    """
    global q_app

    q_app = initPyqtApp()
    initLogging()
    logger.debug("QApplication and logging initialized")
    setConfigurations()
    # vApplication = VardaApplication()
    # Initialize the core components
    sessionContext = VardaSessionContext()

    varda.app.proj = sessionContext.proj
    varda.app.registry = sessionContext.registry
    varda.app.pm = sessionContext.pm

    # let plugins run their startup code -- can only be done after the app api has been set up
    sessionContext.pm.hook.onLoad()

    # Initialization complete -- start GUI
    logger.info("Varda initialized successfully!")
    startGUI()


if __name__ == "__main__":
    initVarda()
