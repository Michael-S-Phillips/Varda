"""
Entrypoint for Varda
This module initializes all the core components of Varda right away, and then starts the GUI.
"""

import sys

import pyqtgraph as pg
from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtWidgets import QApplication, QSplashScreen
from PyQt6.QtCore import QSize

import varda
from varda._actions import MENUBAR
from varda.app import VardaApplication
from varda.maingui import MainGUI


import ctypes

if sys.platform == "win32":
    # this "registers" varda as its own unique application, which lets it use its own icon for the taskbar, instead of the generic python icon
    appid = "varda.0.1.0"
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(appid)

ICON_PATH = "resources/logo.svg"


def initVarda() -> None:
    """Initialize and start the Varda application."""

    q_app = QApplication(sys.argv)
    q_app.setApplicationName("Varda")
    app_icon = QIcon()
    app_icon.addFile(ICON_PATH, QSize(16, 16))
    q_app.setWindowIcon(app_icon)
    splash = QSplashScreen(QPixmap(ICON_PATH))
    splash.show()
    q_app.processEvents()

    varda.log._initializeFullLogging()

    pg.setConfigOptions(imageAxisOrder="row-major")
    varda.log.debug("Configurations set")

    app = VardaApplication()
    app.pluginManager.hook.onLoad(app=app)

    app.maingui = MainGUI(app=app)
    app.maingui.setModelMenuBar(MENUBAR)
    app.context.changed.connect(
        lambda _keys: app.maingui.menuBar().update_from_context(app.context)
    )
    app.maingui.showMaximized()

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
