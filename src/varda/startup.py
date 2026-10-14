"""Builds the application behind the splash: logging, plugins, the main
window and its wiring. ``varda.main`` imports this once the splash is up."""

from PyQt6.QtWidgets import QApplication

import varda
from varda._actions import MENUBAR
from varda._actions._file_actions import importImagePaths
from varda.all_images_view_list.image_list_menu_controller import (
    ImageListMenuController,
)
from varda.app import VardaApplication
from varda.maingui import MainGUI
from varda.session_autosave import SessionAutosaver


def createVarda(q_app: QApplication) -> VardaApplication:
    """Build the application and show its main window. The splash animates
    while this runs on the GUI thread, so it repaints between stages."""
    varda.log._initializeFullLogging()
    q_app.processEvents()


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
    return app
