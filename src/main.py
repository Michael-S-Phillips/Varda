from pathlib import Path
from gui import maingui
from datetime import datetime
import logging
import os


def initLogging():
    """
    Setup logging. Logs will be saved in the "logs" directory. with a unique timestamp

    Usage: create a logger object in any file and use it to log messages, e.g.

      import logging
      logger = logging.getLogger(__name__)
      logger.debug("This is a debug message")
      logger.info("This is an info message")
      logger.warning("This is a warning message")
      logger.error("This is an error message")
    """
    logFolder = "logs"
    os.makedirs(logFolder, exist_ok=True)
    logTime = datetime.now().strftime('%Y-%m-%d_%I-%M-%S-%p')
    logging.basicConfig(filename=Path(f"{logFolder}/VardaLog_{logTime}.log"),
                        level=logging.DEBUG)


if __name__ == "__main__":
    initLogging()
    maingui.startGui()

