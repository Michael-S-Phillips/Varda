"""
Entrypoint for Varda
This module initializes all the core components of Varda right away, and then starts the GUI.
"""

# standard library
from datetime import datetime
import logging
from pathlib import Path
import sys

# third party imports
from PyQt6.QtCore import QStandardPaths
from PyQt6.QtGui import QPixmap, QAction
from PyQt6.QtWidgets import QApplication, QSplashScreen
import pyqtgraph as pg

# local imports
import varda
from varda.maingui import MainGUI
from varda.common.widgets import VardaMenuBar, StatusBar
from varda.plugins import VardaPluginManager
from varda.project import ProjectContext
from varda.project.project_io import ProjectJsonIO
from varda.registries.registries import VardaRegistries


class VardaApplication:
    def __init__(self, proj, pm, registry):
        self.proj = proj
        self.pm = pm
        self.registry = registry


def quitApp():
    varda.log.info("Exiting application...")
    QApplication.instance().quit()


# temp thing for now. Eventually going to make an action registry / manager class
actions = []


def createAction(name: str, callback, shortcut=None):
    action = QAction(name)
    # we wrap the calback in a lambda to avoid passing the "checked" bool argument that the triggered signal emits
    action.triggered.connect(lambda: callback())
    if shortcut:
        action.setShortcut(shortcut)
    return action


def initMenuBar(app):
    ### Initialize Actions ###
    importImageAction = createAction("Import Image", app.proj.loadNewImage, "Ctrl+N")
    saveProjectAction = createAction("Save Project", app.proj.saveProject, "Ctrl+S")
    openProjectAction = createAction("Open Project", app.proj.loadProject, "Ctrl+O")
    exitAppAction = createAction("Exit", quitApp)
    dumpProjectDataAction = createAction(
        "Dump Project Data",
        lambda: varda.utilities.debug.ProjectContextDataTable(app.proj, None),
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


def initVarda() -> None:
    """
    Initialize and start the Varda application.
    """

    #### Initialize PyQt Application ###
    # Initialize the QApplication
    q_app = QApplication(sys.argv)
    q_app.setApplicationName("Varda")
    q_app.setOrganizationName("Varda")
    splash = QSplashScreen(QPixmap("resources/logo.svg"))
    splash.show()
    q_app.processEvents()  # ensures splash screen is shown

    ### Initialize Logging -- Logs stored in user's local appdata folder ###
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
    varda.log.debug("QApplication and logging initialized")

    ### Set Configurations ###
    pg.setConfigOptions(imageAxisOrder="row-major")
    varda.log.debug("Configurations set")

    ### Initialize Application Components ###
    app = VardaApplication(
        ProjectContext(io=ProjectJsonIO()), VardaPluginManager(), VardaRegistries()
    )
    # let plugins run their startup code
    app.pm.hook.onLoad(app=app)

    ### Initialization complete ###
    varda.log.info("Varda initialized successfully!")

    ### start GUI ###
    gui = MainGUI(app, initMenuBar(app), StatusBar(app.proj))
    gui.showMaximized()
    splash.finish(gui)
    varda.log.debug("starting the GUI event loop...")
    exitCode = q_app.exec()
    varda.log.info("Application exiting, performing cleanup...")
    sys.exit(exitCode)


if __name__ == "__main__":
    initVarda()
