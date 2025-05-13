"""
Main entry point for the application.
This file is responsible for setting up logging and starting the GUI.
"""

# standard library
from pathlib import Path
from datetime import datetime
import logging
import sys
import os
import atexit

# third party imports
import pyqtgraph as pg
from PyQt6.QtWidgets import QApplication

# local imports
from gui import maingui
from core.data import ProjectContext


def initLogging():
    """Setup logging. Logs will be saved in the "logs" directory. with a unique timestamp

    Usage: create a logger object in any file and use it to log messages, e.g.

      import logging
      logger = logging.getLogger(__name__)
      logger.debug("This is a debug message")
      logger.info("This is an info message")
      logger.warning("This is a warning message")
      logger.error("This is an error message")
    """

    logFolder = "../logs"
    os.makedirs(logFolder, exist_ok=True)
    logTime = datetime.now().strftime("%Y-%m-%d_%I-%M-%S-%p")
    logName = Path(f"{logFolder}/Varda.log.{logTime}")
    logging.basicConfig(
        level=logging.DEBUG,
        handlers=[logging.FileHandler(logName), logging.StreamHandler(sys.stdout)],
    )


def setupConfig():
    """Any configuration settings that need to be applied before starting the program goes here"""
    pg.setConfigOptions(imageAxisOrder="row-major")


def cleanup():
    """Clean up resources before application exit."""
    logging.info("Application exiting, performing cleanup...")
    # Force any remaining QApplication instances to quit
    app = QApplication.instance()
    if app:
        app.quit()


if __name__ == "__main__":
    initLogging()
    setupConfig()
    
    # Register cleanup function to be called on exit
    atexit.register(cleanup)
    
    proj = ProjectContext()
    try:
        maingui.startGui(proj)
    except Exception as e:
        logging.error(f"Error in main application: {e}", exc_info=True)
        sys.exit(1)