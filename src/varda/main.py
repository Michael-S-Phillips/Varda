"""
Entrypoint for Varda.

Shows the splash before anything else: importing the application takes a few
seconds, so this module imports only what the splash needs, and ``main``
imports the rest once the splash is on screen.
"""

import ctypes
import importlib
import os
import sys
import threading

from PyQt6.QtCore import QSize
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

import varda
from varda.branding.splash import createSplash
from varda.utilities.resources import resource_path

if sys.platform == "win32":
    # this "registers" varda as its own unique application, which lets it use its own icon for the taskbar, instead of the generic python icon.
    # Kept free of the version, so taskbar pins survive updates.
    appid = "varda"
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(appid)

ICON_PATH = resource_path("resources/logo.svg")
SELF_TEST_FLAG = "--self-test"
# Where the self-test writes its report when the app has no console (the
# windowed Windows app); the release build reads it from here
SELF_TEST_REPORT_ENV = "VARDA_SELF_TEST_REPORT"
SELF_TEST_REPORT_DEFAULT = "varda-self-test.txt"
FRAME_SECONDS = 0.016

# Libraries without Qt that most of the import time goes to. They load on a
# worker thread while this thread keeps the splash animating.
PRELOAD = (
    "numpy",
    "scipy.ndimage",
    "scipy.signal",
    "scipy.stats",
    "pandas",
    "geopandas",
    "shapely",
    "pyproj",
    "rasterio",
    "numba",
    "spectral",
    "torch",  # only when installed in Varda's own environment (the ml extra)
)


def _preload(q_app: QApplication) -> None:
    """Import ``PRELOAD`` in the background, repainting the splash meanwhile."""

    def load() -> None:
        for name in PRELOAD:
            try:
                importlib.import_module(name)
            except ImportError:
                pass  # the real import later reports it properly

    worker = threading.Thread(target=load, name="preload", daemon=True)
    worker.start()
    while worker.is_alive():
        q_app.processEvents()
        worker.join(FRAME_SECONDS)


def _consoleForSelfTest() -> None:
    """A windowed Windows app has no stdout or stderr, so the self-test's
    report would vanish; send it to a file instead."""
    if SELF_TEST_FLAG in sys.argv and sys.stdout is None:
        report = open(  # noqa: SIM115 (open for the life of the process)
            os.environ.get(SELF_TEST_REPORT_ENV, SELF_TEST_REPORT_DEFAULT),
            "w",
            encoding="utf-8",
        )
        sys.stdout = sys.stderr = report


def main():
    _consoleForSelfTest()
    q_app = QApplication(sys.argv)
    q_app.setApplicationName("Varda")
    appIcon = QIcon()
    appIcon.addFile(ICON_PATH, QSize(16, 16))
    q_app.setWindowIcon(appIcon)
    splash = createSplash()
    splash.show()
    q_app.processEvents()
    _preload(q_app)

    # Imported here, not at the top, so the splash is up while they load
    from varda.startup import createVarda

    app = createVarda(q_app)
    if SELF_TEST_FLAG in sys.argv:
        from varda.self_test import runSelfTest

        sys.exit(runSelfTest(app))
    assert app.maingui is not None  # createVarda builds and shows it
    splash.finishWhenDone(app.maingui)
    varda.log.info("starting the GUI event loop...")
    exitCode = q_app.exec()
    varda.log.info("Application exiting, performing cleanup...")
    sys.exit(exitCode)


if __name__ == "__main__":
    main()
