# standard library
from typing import Callable, List
from pathlib import Path
import logging
import importlib
import pkgutil


# third party imports
from PyQt6.QtCore import pyqtSignal, QObject, QThreadPool, QRunnable
from PyQt6.QtWidgets import QFileDialog

# local imports
from core.utilities.load_image.loaders import AbstractImageLoader


logger = logging.getLogger(__name__)


# TODO: redo system so each loader is just a module instead using classes and inheritance
'''
# WIP of the above idea:

LOADERS_PACKAGE_NAME = "loaders"
def getAllImageLoaders():
    """Dynamically import all modules in a package and return a dict of module names to modules."""
    modules = {}
    pkg = importlib.import_module(LOADERS_PACKAGE_NAME)

    for _, module_name, _ in pkgutil.iter_modules(pkg.__path__):
        full_module_name = f"{LOADERS_PACKAGE_NAME}.{module_name}"
        module = importlib.import_module(full_module_name)

        if not hasattr(module, "load"):
            logger.warning(f"Module {full_module_name} has no load() function. Ignoring.")
            continue
        modules[module_name] = module

    return modules
# Usage:
imageLoaders = getAllImageLoaders()
# Calling load function of a specific module
image_data = imageLoaders["jpeg_loader"].load("image.jpg")
'''


class ImageLoadingService:
    """Handles image loading in a background thread using QThreadPool.
    public methods:
        loadImageData - loads raster and metadata from an image file and return it.
    """

    def __init__(self):
        self.threadPool = QThreadPool()  # Global thread pool
        self.activeLoadingProcesses = []  # Track active processes

    def loadImageData(self, filePath=None, onSuccessCallback=None):
        """Loads a new image and adds it to the project.

        If filePath is None, prompts the user to select a file using a file dialog.
        Calls onSuccessCallback after the image is loaded.
        onSuccessCallback should accept two arguments: the array of raster data, and a Metadata Object.
        Returns:
            (raster, metadata): Data from the image file
        """
        if filePath is None:
            filePath = self._requestFilePath()
            if filePath is None:
                # if user closed file dialog without selecting a file.
                logger.info("No file path provided.")
                return
        try:
            loader = self._getLoader(filePath)
            self._createNewLoadProcess(loader, filePath, onSuccessCallback)
        except ValueError as e:
            logger.error(f"Error loading image: {e}")

    def _requestFilePath(self):
        """Opens a file dialog to request an image file path from the user."""
        fileName, _ = QFileDialog.getOpenFileName(
            None,
            "Open File",
            "",
            "image file (*.hdr *.img *.h5)",
        )
        return fileName if fileName else None

    def _getLoader(self, filePath):
        """Finds the correct image loader based on the file type."""
        imageType = Path(filePath).suffix.strip()
        for loader in AbstractImageLoader.subclasses:
            if imageType in loader.imageType:
                return loader()
        raise ValueError(f"Unsupported file type: {imageType}")

    def _createNewLoadProcess(self, loader, filePath, onSuccessCallback):
        """Creates and starts a new image loading process in the thread pool."""
        logger.info(f"Creating new image loading process for {filePath}")
        process = self.ImageLoadProcess(loader, filePath, onSuccessCallback)
        process.signals.sigFinished.connect(self._onLoadingProcessFinished)
        self.activeLoadingProcesses.append(process)
        self.threadPool.start(process)

    def _onLoadingProcessFinished(self, loadingProcess):
        """Handles post-processing once the image is loaded."""
        self.activeLoadingProcesses.remove(loadingProcess)  # Cleanup
        raster, metadata = loadingProcess.result
        logger.info(f"Done loading image: {metadata.filePath}")
        loadingProcess.onSuccessCallback(raster, metadata)  # Call the original callback

    class ImageLoadProcess(QRunnable):
        """Represents a single image loading process running in a thread."""
        class Signals(QObject):
            sigFinished: pyqtSignal = pyqtSignal(object)

        def __init__(self, loader, filePath, onSuccessCallback):
            super().__init__()
            self.loader = loader
            self.filePath = filePath
            self.onSuccessCallback = onSuccessCallback
            self.signals = self.Signals()
            self.result = None

        def run(self):
            """loads the image from a separate thread. emits signal with a reference to itself when complete."""
            logger.info(f"Loading image: {self.filePath}")
            self.result = self.loader.load(self.filePath)
            logger.info(f"image loading complete: {self.filePath}")
            self.signals.sigFinished.emit(self)
