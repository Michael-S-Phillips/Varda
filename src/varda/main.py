"""
Entrypoint for Varda
This module initializes all the core components of Varda right away, and then starts the GUI.
"""

import sys

import pyqtgraph as pg
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QSize

import varda
from varda._actions import MENUBAR
from varda._actions._file_actions import importImagePaths
from varda.all_images_view_list.image_list_menu_controller import (
    ImageListMenuController,
)
from varda.app import VardaApplication
from varda.branding.splash import createSplash
from varda.maingui import MainGUI
from varda.self_test import FLAG as SELF_TEST_FLAG, runSelfTest
from varda.session_autosave import SessionAutosaver
from varda.utilities.resources import resource_path


import ctypes

if sys.platform == "win32":
    # this "registers" varda as its own unique application, which lets it use its own icon for the taskbar, instead of the generic python icon
    appid = "varda.0.3.1"
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(appid)

ICON_PATH = resource_path("resources/logo.svg")


def createVarda() -> tuple[QApplication, VardaApplication]:
    """Build the application and show its main window."""

    q_app = QApplication(sys.argv)
    q_app.setApplicationName("Varda")
    app_icon = QIcon()
    app_icon.addFile(ICON_PATH, QSize(16, 16))
    q_app.setWindowIcon(app_icon)
    # The splash animates while initialisation runs on this thread, so let
    # it repaint between stages
    splash = createSplash()
    splash.show()
    q_app.processEvents()

    varda.log._initializeFullLogging()
    q_app.processEvents()

    pg.setConfigOptions(imageAxisOrder="row-major")
    varda.log.debug("Configurations set")

    app = VardaApplication()
    app.pluginManager.hook.onLoad(app=app)
    q_app.processEvents()

    app.maingui = MainGUI(app=app)
    q_app.processEvents()
    app.maingui.setModelMenuBar(MENUBAR)
    imageListController = ImageListMenuController(app, parent=app.maingui)
    app.maingui.imageList.sigImagesActivated.connect(
        imageListController.onImagesActivated
    )
    app.maingui.imageList.sigContextMenuRequested.connect(
        imageListController.onContextMenuRequested
    )
    # Files dragged onto the window import like File > Import Image(s)
    app.maingui.sigFilesDropped.connect(
        lambda paths: importImagePaths(paths, app.images)
    )
    app.context.changed.connect(
        lambda _keys: app.maingui.menuBar().update_from_context(app.context)
    )
    # Autosave the session every few minutes and on quit (File > Restore Last Session)
    app.autosaver = SessionAutosaver(app.images, app.maingui, parent=app.maingui)
    app.maingui.showMaximized()
    q_app.processEvents()

    varda.log.info("Varda initialized successfully!")

    splash.finishWhenDone(app.maingui)
    return q_app, app


def initVarda() -> None:
    """Initialize and start the Varda application."""
    q_app, _app = createVarda()
    varda.log.info("starting the GUI event loop...")
    exitCode = q_app.exec()
    varda.log.info("Application exiting, performing cleanup...")
    sys.exit(exitCode)


def main():
    if SELF_TEST_FLAG in sys.argv:
        _q_app, app = createVarda()
        sys.exit(runSelfTest(app))
    initVarda()


if __name__ == "__main__":
    main()
