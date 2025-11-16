"""
Entrypoint for Varda
This module initializes all the core components of Varda right away, and then starts the GUI.
"""

# standard library
import sys

import pyqtgraph as pg

# third party imports
from PyQt6.QtCore import QObject
from PyQt6.QtGui import QAction, QPixmap
from PyQt6.QtWidgets import QApplication, QSplashScreen

# local imports
import varda
from varda.common.observable_list import ObservableList
from varda.common.widgets import StatusBar, VardaMenuBar
from varda.image_loading import ImageLoadingService
from varda.maingui import MainGUI
from varda.new_workspace_dialog import NewWorkspaceDialog
from varda.plugins import VardaPluginManager
from varda.project import ProjectContext
from varda.project.project_io import ProjectJsonIO
from varda.registries.registries import VardaRegistries


class VardaApplicationContext(QObject):
    def __init__(self, proj, pm, registry):
        super().__init__()
        self.proj = proj
        self.pm = pm
        self.registry = registry
        self.images = ObservableList()

        self._imageLoadingService = ImageLoadingService()

    def loadNewImage(self):
        self._imageLoadingService.load_image_data(
            on_success_callback=self.images.append
        )


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
    importImageAction = createAction("Import Image", app.loadNewImage, "Ctrl+N")
    saveProjectAction = createAction("Save Project", app.proj.saveProject, "Ctrl+S")
    openProjectAction = createAction("Open Project", app.proj.loadProject, "Ctrl+O")
    exitAppAction = createAction("Exit", quitApp)
    dumpProjectDataAction = createAction(
        "Dump Project Data",
        lambda: varda.utilities.debug.ProjectContextDataTable(app.proj, None),
    )
    # debug actions
    loadDummyImageAction = createAction(
        "Load Dummy Image",
        lambda: varda.utilities.debug.loadRandomImageIntoProject(
            app, (100, 100, 50), (10, 10, 10)
        ),
        "F11",
    )
    newWorkspaceCreator = createAction(
        "New Workspace Creator", lambda: NewWorkspaceDialog(app.images).exec()
    )
    actions.append(importImageAction)
    actions.append(saveProjectAction)
    actions.append(openProjectAction)
    actions.append(exitAppAction)
    actions.append(dumpProjectDataAction)
    actions.append(loadDummyImageAction)
    actions.append(newWorkspaceCreator)
    ### Initialize MenuBar ###
    menuBar = VardaMenuBar()
    menuBar.registerAction("File", importImageAction)
    menuBar.registerAction("File", saveProjectAction)
    menuBar.registerAction("File", openProjectAction)
    menuBar.registerAction("File", exitAppAction)
    menuBar.registerAction("Debug", dumpProjectDataAction)
    menuBar.registerAction("Debug", loadDummyImageAction)
    menuBar.registerAction("Debug", newWorkspaceCreator)
    return menuBar


def initVarda() -> None:
    """
    Initialize and start the Varda application.
    """

    #### Initialize PyQt Application ###
    # Initialize the QApplication
    q_app = QApplication(sys.argv)
    q_app.setApplicationName("Varda")
    splash = QSplashScreen(QPixmap("resources/logo.svg"))
    splash.show()
    q_app.processEvents()  # ensures splash screen is shown

    ### Initialize Logging -- Logs stored in user's local appdata folder ###
    varda.log._initializeFullLogging()

    ### Set Configurations ###
    pg.setConfigOptions(imageAxisOrder="row-major")
    varda.log.debug("Configurations set")

    ### Initialize Application Components ###
    app = VardaApplicationContext(
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


def main():
    initVarda()


if __name__ == "__main__":
    main()
