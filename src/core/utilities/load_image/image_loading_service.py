# standard library
from typing import Callable, List, Dict, Optional
from pathlib import Path
import logging
import importlib
import pkgutil
from enum import Enum
import traceback

# third party imports
from PyQt6.QtCore import pyqtSignal, QObject, QThreadPool, QRunnable, QTimer
from PyQt6.QtWidgets import QFileDialog, QMessageBox

from core.entities import Metadata

# local imports
from core.utilities.load_image.loaders import AbstractImageLoader


logger = logging.getLogger(__name__)


class ImageLoadingService:
    """Handles image loading in a background thread using QThreadPool.
    
    public methods:
        loadImageData - loads raster and metadata from an image file and return it.
    """

    class LoadStatus(Enum):
        LOAD = 0
        SUCCESS = 1
        FAIL = 2
        WARNING = 3  # New status for partial success with warnings

    def __init__(self):
        self.threadPool = QThreadPool()  # Global thread pool
        self.activeLoadingProcesses = []  # Track active processes
        self.loadTimeoutMs = 30000  # Timeout for loading (30 seconds)

    # public methods
    def loadImageData(self, filePath=None, onSuccessCallback=None, onFailureCallback=None):
        """Loads a new image and adds it to the project.

        If filePath is None, prompts the user to select a file using a file dialog.
        Calls onSuccessCallback after the image is loaded.
        onSuccessCallback should accept two arguments: the array of raster data, and a Metadata Object.
        
        Args:
            filePath: Path to the image file. If None, prompts user to select a file.
            onSuccessCallback: Function to call on successful load, receives (raster, metadata).
            onFailureCallback: Function to call on load failure, receives error message.
            
        Returns:
            (raster, metadata): Data from the image file, or None if loading fails
        """
        if filePath is None:
            filePath = self._requestFilePath()
            if filePath is None:
                # if user closed file dialog without selecting a file.
                logger.info("No file path provided.")
                return
        try:
            loader = self._getLoader(filePath)
            self._createNewLoadProcess(loader, filePath, onSuccessCallback, onFailureCallback)
        except ValueError as e:
            logger.error(f"Error loading image: {e}")
            if onFailureCallback:
                onFailureCallback(str(e))
            else:
                self._showErrorMessage(f"Error loading image: {e}")

    @staticmethod
    def getImageTypeFilter():
        """Returns a list of file filters for the image file dialog."""
        filters = "Image File ("
        for loader in AbstractImageLoader.subclasses:
            for imageType in loader.imageType:
                if isinstance(imageType, str):
                    filters += f"*{imageType} "
                elif isinstance(imageType, tuple):
                    for imgType in imageType:
                        filters += f"*{imgType} "
        filters = filters.strip() + ")"
        return filters

    # private methods
    def _createNewLoadProcess(self, loader, filePath, onSuccessCallback, onFailureCallback):
        """Creates and starts a new image loading process in the thread pool."""
        logger.info(f"Creating new image loading process for {filePath}")
        process = self.ImageLoadProcess(loader, filePath, onSuccessCallback, onFailureCallback)
        process.signals.sigFinished.connect(self._onLoadingProcessFinished)
        
        # Set up a timeout for the loading process
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self._handleLoadTimeout(process))
        timer.start(self.loadTimeoutMs)
        process.timer = timer
        
        self.activeLoadingProcesses.append(process)
        self.threadPool.start(process)

    def _handleLoadTimeout(self, process):
        """Handle a loading process timeout."""
        if process in self.activeLoadingProcesses:
            logger.error(f"Image loading timeout for {process.filePath}")
            self.activeLoadingProcesses.remove(process)
            if process.onFailureCallback:
                process.onFailureCallback("Loading timed out. The file may be too large or corrupted.")
            else:
                self._showErrorMessage(f"Loading timed out for {process.filePath}. The file may be too large or corrupted.")

    def _onLoadingProcessFinished(self, loadingProcess):
        """Handles cleanup and callback (if success) once the image is loaded."""
        # Cancel the timeout timer
        if hasattr(loadingProcess, 'timer') and loadingProcess.timer.isActive():
            loadingProcess.timer.stop()
            
        if loadingProcess in self.activeLoadingProcesses:
            self.activeLoadingProcesses.remove(loadingProcess)  # Cleanup
            
            if loadingProcess.status == ImageLoadingService.LoadStatus.SUCCESS:
                raster, metadata = loadingProcess.result
                logger.info(f"Done loading image: {metadata.filePath}")
                
                # Check if there are load warnings
                loadErrors = getattr(loadingProcess.loader, '_loadErrors', [])
                
                if loadErrors and loadingProcess.onSuccessCallback:
                    # We still load the image but with warnings
                    loadingProcess.status = ImageLoadingService.LoadStatus.WARNING
                    self._showWarningMessage(
                        f"Image loaded with warnings:\n\n{chr(10).join(loadErrors[:5])}" +
                        (f"\n... and {len(loadErrors) - 5} more issues" if len(loadErrors) > 5 else "")
                    )
                    
                if loadingProcess.onSuccessCallback:
                    loadingProcess.onSuccessCallback(raster, metadata)
                    
            elif loadingProcess.status == ImageLoadingService.LoadStatus.FAIL:
                error_msg = str(loadingProcess.error) if hasattr(loadingProcess, 'error') else "Unknown error"
                logger.error(f"Image loading failed: {error_msg}")
                
                if loadingProcess.onFailureCallback:
                    loadingProcess.onFailureCallback(error_msg)
                else:
                    self._showErrorMessage(f"Failed to load image: {error_msg}")

    def _showErrorMessage(self, message):
        """Display an error message to the user."""
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setWindowTitle("Error Loading Image")
        msg_box.setText(message)
        msg_box.exec()

    def _showWarningMessage(self, message):
        """Display a warning message to the user."""
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setWindowTitle("Image Loaded with Warnings")
        msg_box.setText(message)
        msg_box.exec()

    # private helpers
    @staticmethod
    def _requestFilePath():
        """Opens a file dialog to request an image file path from the user."""
        fileName, _ = QFileDialog.getOpenFileName(
            None,
            "Open File",
            "",
            ImageLoadingService.getImageTypeFilter(),
        )
        return fileName if fileName else None

    @staticmethod
    def _getLoader(filePath):
        """Finds the correct image loader based on the file type."""
        imageType = Path(filePath).suffix.lower()
        for loader in AbstractImageLoader.subclasses:
            loaderTypes = loader.imageType
            if isinstance(loaderTypes, str):
                loaderTypes = [loaderTypes]
            
            if any(imageType == t.lower() for t in loaderTypes):
                return loader()
        
        # If no specific loader found, try to infer from file content
        # TODO: Implement content-based detection if needed
        
        raise ValueError(f"Unsupported file type: {imageType}")

    class ImageLoadProcess(QRunnable):
        """Represents a single image loading process running in a thread."""

        class Signals(QObject):
            sigFinished: pyqtSignal = pyqtSignal(object)

        def __init__(self, loader, filePath, onSuccessCallback, onFailureCallback):
            super().__init__()
            self.loader = loader
            self.filePath = filePath
            self.onSuccessCallback = onSuccessCallback
            self.onFailureCallback = onFailureCallback
            self.signals = self.Signals()
            self.result = None
            self.error = None
            self.status = ImageLoadingService.LoadStatus.LOAD

        def run(self):
            """loads the image from a separate thread. emits signal with a reference to itself when complete."""
            logger.info(f"Loading image: {self.filePath}")
            try:
                self.result = self.loader.load(self.filePath)
                self.status = ImageLoadingService.LoadStatus.SUCCESS
                logger.info(f"Image loading Success: {self.filePath}")
            except Exception as e:
                self.status = ImageLoadingService.LoadStatus.FAIL
                self.error = e
                logger.error(f"Image loading Failed: {str(e)}")
                logger.error(traceback.format_exc())
            finally:
                self.signals.sigFinished.emit(self)