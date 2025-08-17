# standard library
import os
import numpy as np
from pathlib import Path
import logging
from enum import Enum
import traceback

# third party imports
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QThreadPool, QRunnable, QTimer
from PyQt6.QtWidgets import (
    QFileDialog,
    QMessageBox,
    QProgressDialog,
    QApplication,
    QDialog,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QButtonGroup,
    QHBoxLayout,
)

import varda.app
from varda.core.entities import GeoReferencer
from varda_rewrite.utilities.dialog_utils import DialogUtils

# TODO: Update these imports when loaders are moved

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
        self.loadTimeoutMs = 120000  # Increase timeout to 120 seconds (2 minutes)
        self.largeFileThresholdMB = (
            100  # Files larger than this will use an extended timeout
        )
        self.largeFileTimeoutMs = 600000  # 10 minutes for very large files

    # public methods
    def _getFileSize(self, filePath):
        """Get file size in megabytes"""
        try:
            return os.path.getsize(filePath) / (1024 * 1024)  # Convert to MB
        except:
            return 0

    def loadImageData(
        self, filePath=None, onSuccessCallback=None, onFailureCallback=None
    ):
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

        # Check file size and adjust timeout
        file_size_mb = self._getFileSize(filePath)
        timeout_ms = self.loadTimeoutMs
        progress_dialog = None

        if file_size_mb > self.largeFileThresholdMB:
            timeout_ms = self.largeFileTimeoutMs
            logger.info(
                f"Large file detected ({file_size_mb:.2f} MB), using extended timeout"
            )

            # Show progress dialog for large files
            progress_dialog = self._showLargeFileLoadingDialog(filePath, timeout_ms)
        try:
            loader = self._getLoader(filePath)

            # Wrap the callbacks to handle the progress dialog
            original_success = onSuccessCallback
            original_failure = onFailureCallback

            def success_with_dialog(raster, metadata):
                if progress_dialog:
                    progress_dialog.close()
                if original_success:
                    original_success(raster, metadata)

            def failure_with_dialog(error_msg):
                if progress_dialog:
                    progress_dialog.close()
                if original_failure:
                    original_failure(error_msg)
                else:
                    self._showErrorMessage(error_msg)

            self._createNewLoadProcess(
                loader, filePath, success_with_dialog, failure_with_dialog, timeout_ms
            )
            if progress_dialog:
                progress_dialog.exec()  # Show the progress dialog and wait for it to finish

        except ValueError as e:
            if progress_dialog:
                progress_dialog.close()
            logger.error(f"Error loading image: {e}")
            if onFailureCallback:
                onFailureCallback(str(e))
            else:
                self._showErrorMessage(f"Error loading image: {e}")

    def loadMetadataOnly(
        self, filePath, onSuccessCallback=None, onFailureCallback=None
    ):
        """
        Load only the metadata for an image file without loading the full raster data.

        This is useful for very large files where we want to inspect the metadata before
        deciding whether to load the full file.

        Args:
            filePath: Path to the image file
            onSuccessCallback: Function to call on successful load, receives (metadata)
            onFailureCallback: Function to call on load failure, receives error message
        """
        if filePath is None:
            filePath = self._requestFilePath()
            if filePath is None:
                return

        try:
            loader = self._getLoader(filePath)

            # Create a small temporary array just to satisfy the metadata loader
            temp_array = np.zeros((1, 1, 3), dtype=np.uint8)

            # Load metadata
            try:
                metadata = loader.loadMetadata(temp_array, filePath)
                if onSuccessCallback:
                    onSuccessCallback(metadata)
            except Exception as e:
                logger.error(f"Error loading metadata: {e}")
                if onFailureCallback:
                    onFailureCallback(f"Error loading metadata: {e}")
                else:
                    self._showErrorMessage(f"Error loading metadata: {e}")

        except ValueError as e:
            logger.error(f"Error finding loader: {e}")
            if onFailureCallback:
                onFailureCallback(str(e))
            else:
                self._showErrorMessage(f"Error loading image: {e}")

    @staticmethod
    def getImageTypeFilter():
        """Returns a list of file filters for the image file dialog."""
        filters = "Image File ("
        for _, loader in varda.app.registry.imageLoaders:
            for extension in loader.imageType:
                filters += f"*{extension} "
        filters = filters.strip() + ")"
        return filters

    # private methods
    def _showLargeFileOptionsDialog(self, filePath, file_size_mb):
        """
        Show a dialog with options for loading a large file

        Returns:
            str: One of 'full', 'preview', 'metadata', or 'cancel'
        """
        message = (
            f"The file you're trying to load is very large ({file_size_mb:.1f} MB).\n"
            "Loading large files may take a long time and use significant memory."
        )
        
        options = [
            "Load a downsampled preview (faster, less memory)",
            "Load the full file (slow, high memory usage)",
            "Load metadata only (fastest)"
        ]
        
        result = DialogUtils.showOptionsDialog(
            title="Large File Detected",
            message=message,
            options=options,
            default_option=0,
            parent=QApplication.activeWindow()
        )
        
        if result == options[0]:
            return "preview"
        elif result == options[1]:
            return "full"
        elif result == options[2]:
            return "metadata"
            
        return "cancel"

    def _createNewLoadProcess(
        self, loader, filePath, onSuccessCallback, onFailureCallback, timeout_ms=None
    ):
        """Creates and starts a new image loading process in the thread pool."""
        logger.info(f"Creating new image loading process for {filePath}")
        process = self.ImageLoadProcess(
            loader, filePath, onSuccessCallback, onFailureCallback
        )
        process.signals.sigFinished.connect(self._onLoadingProcessFinished)

        # Set up a timeout for the loading process
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self._handleLoadTimeout(process))

        # Use custom timeout if provided, otherwise use the default
        if timeout_ms is None:
            timeout_ms = self.loadTimeoutMs

        timer.start(timeout_ms)
        process.timer = timer

        self.activeLoadingProcesses.append(process)
        self.threadPool.start(process)

    def _handleLoadTimeout(self, process):
        """Handle a loading process timeout."""
        if process in self.activeLoadingProcesses:
            logger.error(f"Image loading timeout for {process.filePath}")
            self.activeLoadingProcesses.remove(process)
            if process.onFailureCallback:
                process.onFailureCallback(
                    "Loading timed out. The file may be too large or corrupted."
                )
            else:
                self._showErrorMessage(
                    f"Loading timed out for {process.filePath}. The file may be too large or corrupted."
                )

    def _onLoadingProcessFinished(self, loadingProcess):
        """Handles cleanup and callback (if success) once the image is loaded."""
        # Cancel the timeout timer
        if hasattr(loadingProcess, "timer") and loadingProcess.timer.isActive():
            loadingProcess.timer.stop()

        if loadingProcess in self.activeLoadingProcesses:
            self.activeLoadingProcesses.remove(loadingProcess)  # Cleanup

            if loadingProcess.status == ImageLoadingService.LoadStatus.SUCCESS:
                raster, metadata = loadingProcess.result
                if metadata.hasGeospatialData:
                    try:
                        metadata.geoReferencer = GeoReferencer(
                            metadata.transform, metadata.crs
                        )
                        logger.debug(
                            f"Successfully created GeoReferencer for {metadata.filePath}"
                        )
                    except ValueError as e:
                        logger.warning(
                            f"Could not create GeoReferencer for {metadata.filePath}: {e}"
                        )
                        metadata.geoReferencer = None
                        # Add this to the metadata's extra metadata for user visibility
                        if not hasattr(metadata, "extraMetadata"):
                            metadata.extraMetadata = {}
                        metadata.extraMetadata["geo_referencing_error"] = str(e)
                logger.info(f"Done loading image: {metadata.filePath}")

                # Check if there are load warnings
                loadErrors = getattr(loadingProcess.loader, "_loadErrors", [])

                if loadErrors and loadingProcess.onSuccessCallback:
                    # We still load the image but with warnings
                    loadingProcess.status = ImageLoadingService.LoadStatus.WARNING
                    self._showWarningMessage(
                        f"Image loaded with warnings:\n\n{chr(10).join(loadErrors[:5])}"
                        + (
                            f"\n... and {len(loadErrors) - 5} more issues"
                            if len(loadErrors) > 5
                            else ""
                        )
                    )

                if loadingProcess.onSuccessCallback:
                    loadingProcess.onSuccessCallback(raster, metadata)

            elif loadingProcess.status == ImageLoadingService.LoadStatus.FAIL:
                error_msg = (
                    str(loadingProcess.error)
                    if hasattr(loadingProcess, "error")
                    else "Unknown error"
                )
                logger.error(f"Image loading failed: {error_msg}")

                if loadingProcess.onFailureCallback:
                    loadingProcess.onFailureCallback(error_msg)
                else:
                    self._showErrorMessage(f"Failed to load image: {error_msg}")

    def _showLargeFileLoadingDialog(self, filePath, timeout_ms):
        """Show a dialog with progress information for large files"""
        logger.info(f"Showing large file loading dialog for {filePath}")
        file_name = os.path.basename(filePath)
        file_size_mb = self._getFileSize(filePath)
        estimated_seconds = timeout_ms / 1000
        
        label_text = (
            f"Loading large file ({file_size_mb:.1f} MB)...\n"
            f"{file_name}\n\n"
            f"This may take up to {estimated_seconds:.0f} seconds for large files."
        )
        
        return DialogUtils.showIndeterminateProgressDialog(
            title="Loading Large File",
            label_text=label_text,
            cancel_button_text="Cancel",
            parent=QApplication.activeWindow(),
            modal=True,
            auto_close=True,
            auto_reset=True,
            min_duration_ms=1000
        )

    def _showErrorMessage(self, message):
        """Display an error message to the user."""
        DialogUtils.showErrorMessage(message, "Error Loading Image")

    def _showWarningMessage(self, message):
        """Display a warning message to the user."""
        DialogUtils.showWarningMessage(message, "Image Loaded with Warnings")

    def loadImageSync(self, filePath):
        """
        Load an image synchronously and return the result.

        This is a convenience method for simple cases where async loading isn't needed.

        Args:
            filePath: Path to the image file

        Returns:
            tuple: (raster, metadata) on success, or (None, None) on failure
        """
        result = (None, None)

        def onSuccess(raster, metadata):
            nonlocal result
            result = (raster, metadata)

        def onFailure(error_msg):
            logger.error(f"Sync loading failed: {error_msg}")

        self.loadImageData(filePath, onSuccess, onFailure)

        # Wait until loading is complete (not ideal for large files, but works for simple cases)
        import time

        timeout = time.time() + self.loadTimeoutMs / 1000
        while result == (None, None) and time.time() < timeout:
            time.sleep(0.1)

        return result

    # private helpers
    @staticmethod
    def _requestFilePath():
        """Opens a file dialog to request an image file path from the user."""
        return DialogUtils.requestFilePath(
            title="Open File",
            directory="",
            filter=ImageLoadingService.getImageTypeFilter(),
        )

    @staticmethod
    def _getLoader(filePath):
        """Finds the correct image loader based on the file type.

        Args:
            filePath: Path to the image file

        Returns:
            An instance of the appropriate loader

        Raises:
            ValueError: If the file type is not supported
        """

        image_path = Path(filePath)
        file_extension = image_path.suffix.lower()

        # First check the registries for a direct extension match
        for name, loader in varda.app.registry.imageLoaders:

            if file_extension in loader.imageType:
                return loader()
        logger.warning(f"Could not find match in loader registry for {file_extension}")

        # NOTE: under normal circumstances, the below code will never run
        # since the user isn't allowed to select a file extension that isn't already in the registries

        # If no exact match, try content-based detection for common formats
        try:
            import magic

            file_mime = magic.from_file(filePath, mime=True)

            # Map mime types to loaders
            mime_to_loader = {
                "image/tiff": TIFFImageLoader,
                "image/png": PillowImageLoader,
                "image/jpeg": PillowImageLoader,
                "image/bmp": PillowImageLoader,
                "image/gif": PillowImageLoader,
                "application/x-hdf": HDF5ImageLoader,
            }

            if file_mime in mime_to_loader:
                return mime_to_loader[file_mime]()
        except ImportError:
            # python-magic not available, fall back to extension-based detection
            logger.warning(
                "python-magic not available, using extension-based detection only"
            )
        except Exception as e:
            logger.warning(f"Error during content-based detection: {e}")

        # As a fallback, try to use Pillow for common image formats
        try:
            from PIL import Image

            try:
                with Image.open(filePath) as img:
                    # If Pillow can open it, use PillowImageLoader
                    return PillowImageLoader()
            except:
                pass
        except ImportError:
            logger.warning("PIL not available for fallback detection")

        # Last resort: try each loader's static method to see if it works
        for loader_class in varda.app.registry.imageLoaders:
            try:
                # Just try to read a tiny bit to see if it works
                test_mode = getattr(loader_class, "supports_preview", False)
                if test_mode:
                    loader_class.loadRasterData(filePath, loadingMode="preview")
                    return loader_class()
            except Exception:
                continue

        raise ValueError(f"Unsupported file type: {file_extension}")

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
                raster = self.loader.loadRasterData(self.filePath)
                metadata = self.loader.loadMetadata(raster, self.filePath)
                self.result = raster, metadata
                self.status = ImageLoadingService.LoadStatus.SUCCESS
                logger.info(f"Image loading Success: {self.filePath}")
            except Exception as e:
                self.status = ImageLoadingService.LoadStatus.FAIL
                self.error = e
                logger.error(f"Image loading Failed: {str(e)}")
                logger.error(traceback.format_exc())
            finally:
                self.signals.sigFinished.emit(self)
