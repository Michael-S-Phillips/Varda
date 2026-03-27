"""
Entrypoint for Varda
This module initializes all the core components of Varda right away, and then starts the GUI.
"""

import sys

import pyqtgraph as pg
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QApplication, QSplashScreen

import varda
from varda.app import VardaApplication
from varda._actions import registerAllActions, MENUBAR
from varda._actions._context_keys import IMAGE_COUNT
from varda.common.observable_list import ImageList
from varda.maingui import MainGUI


def initVarda() -> None:
    """Initialize and start the Varda application."""

    ### Initialize PyQt Application ###
    q_app = QApplication(sys.argv)
    q_app.setApplicationName("Varda")
    splash = QSplashScreen(QPixmap("resources/logo.svg"))
    splash.show()
    q_app.processEvents()

    ### Initialize Logging ###
    varda.log._initializeFullLogging()

    ### Set Configurations ###
    pg.setConfigOptions(imageAxisOrder="row-major")
    varda.log.debug("Configurations set")

    ### Create Application ###
    app = VardaApplication()

    ### Register DI Providers ###
    app.injection_store.register_provider(lambda: app.images, ImageList)
    app.injection_store.register_provider(lambda: app.maingui, MainGUI)

    ### Initialize Expression Context ###
    app.context[IMAGE_COUNT] = 0

    ### Register Actions ###
    registerAllActions(app)

    ### Load Plugins ###
    app.pm.hook.onLoad(app=app)

    ### Build GUI ###
    app.maingui = MainGUI(app=app)
    app.maingui.setModelMenuBar(MENUBAR)
    app.maingui.showMaximized()

    ### Connect Context Updates ###
    def onImagesChanged(items: list) -> None:
        app.context[IMAGE_COUNT] = len(items)
        app.maingui.menuBar().update_from_context(app.context)

    app.images.sigDataChanged.connect(onImagesChanged)

    ### Initialization Complete ###
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
