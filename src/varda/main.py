"""
Entrypoint for Varda
This module initializes all the core components of Varda right away, and then starts the GUI.
"""

# standard library
import sys

# third party imports
import pyqtgraph as pg
from PyQt6.QtCore import QObject
from PyQt6.QtGui import QAction, QPixmap
from PyQt6.QtWidgets import QApplication, QSplashScreen, QStatusBar

# local imports
import varda
from varda.common.observable_list import ObservableList
from varda.status_bar import StatusBar
from varda.main_menu_bar import VardaMenuBar
from varda.image_loading import ImageLoadingService
from varda.maingui import MainGUI
from varda.workspaces.dual_image_workspace import NewDualImageWorkspaceDialog
from varda.workspaces.general_image_analysis import (
    NewGeneralImageAnalysisWorkspaceDialog,
)
from varda.plugins import VardaPluginManager


class VardaApplicationContext(QObject):
    def __init__(self, pm, maingui: MainGUI = None):
        super().__init__()
        self.pm = pm
        self.maingui = maingui
        self.images = ObservableList()

    def loadNewImage(self):
        ImageLoadingService.load_image_data(on_success_callback=self.images.append)

    def quit(self):
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


def initMenuBar(app: VardaApplicationContext):
    ### Initialize Actions ###
    # This is probably not a long term solution, but it's vaguely in the realm of what we want
    # -- that being a centralized action registry seperate from any specific UI component, that can be injected into menubar and such.
    importImageAction = createAction("Import Image", app.loadNewImage, "Ctrl+N")
    # saveProjectAction = createAction("Save Project", app.saveProject, "Ctrl+S")
    # openProjectAction = createAction("Open Project", app.loadProject, "Ctrl+O")
    exitAppAction = createAction("Exit", app.quit, "Ctrl+Q")
    # dumpProjectDataAction = createAction(
    #     "Dump Project Data",
    #     lambda: varda.utilities.debug.ProjectContextDataTable(app, None),
    # )
    # debug actions
    loadDummyImageAction = createAction(
        "Load Dummy Image",
        lambda: varda.utilities.debug.loadRandomImageIntoProject(app),
        "F11",
    )
    newDualWorkspaceCreator = createAction(
        "New Dual Image Workspace",
        lambda: NewDualImageWorkspaceDialog(app.images)
        .connectOnAccept(
            lambda workspace: app.maingui.addTab(workspace, "Dual Image Workspace")
        )
        .open(),
    )
    newGeneralWorkspaceCreator = createAction(
        "New General Image Analysis Workspace",
        lambda: NewGeneralImageAnalysisWorkspaceDialog(app.images)
        .connectOnAccept(
            lambda workspace: app.maingui.addTab(
                workspace, "General Image Analysis Workspace"
            )
        )
        .open(),
    )

    actions.append(importImageAction)
    # actions.append(saveProjectAction)
    # actions.append(openProjectAction)
    actions.append(exitAppAction)
    # actions.append(dumpProjectDataAction)
    actions.append(loadDummyImageAction)
    actions.append(newDualWorkspaceCreator)
    actions.append(newGeneralWorkspaceCreator)
    ### Initialize MenuBar ###
    menuBar = VardaMenuBar()
    menuBar.registerAction("File", importImageAction)
    # menuBar.registerAction("File", saveProjectAction)
    # menuBar.registerAction("File", openProjectAction)
    menuBar.registerAction("File", exitAppAction)
    # menuBar.registerAction("Debug", dumpProjectDataAction)
    menuBar.registerAction("Debug", loadDummyImageAction)
    menuBar.registerAction("Workspace", newDualWorkspaceCreator)
    menuBar.registerAction("Workspace", newGeneralWorkspaceCreator)
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
    app = VardaApplicationContext(VardaPluginManager())

    # let plugins run their startup code
    app.pm.hook.onLoad(app=app)

    ### build GUI ###
    menuBar = initMenuBar(app)
    app.maingui = MainGUI(app, menuBar, QStatusBar())
    app.maingui.showMaximized()

    ### Initialization complete ###
    varda.log.info("Varda initialized successfully!")

    splash.finish(app.maingui)
    varda.log.info("starting the GUI event loop...")
    exitCode = q_app.exec()
    varda.log.info("Application exiting, performing cleanup...")
    sys.exit(exitCode)


def main():
    initVarda()


if __name__ == "__main__":
    main()
