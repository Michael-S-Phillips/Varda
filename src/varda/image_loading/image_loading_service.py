# standard library
import os
from pathlib import Path
from dataclasses import dataclass
import logging
from enum import Enum
import traceback
from typing import Type

# third party imports
import numpy as np
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
from varda.common.entities.geo_referencer import GeoReferencer
from .protocols import ImageLoaderProtocol
from ..common.entities import Image

# TODO: Update these imports when loaders are moved

logger = logging.getLogger(__name__)


@dataclass
class RegisteredLoader:
    formatName: str
    fileExtensions: tuple[str]
    loaderClass: Type[ImageLoaderProtocol]


_loader_registry: list[RegisteredLoader] = []


def register_image_loader(formatName: str, fileExtensions: str | list | tuple):
    """Decorator to register an ImageLoader for specific file extensions."""

    def decorator(cls):
        if not issubclass(cls, ImageLoaderProtocol):
            raise TypeError("Class must implement the ImageLoader Protocol")

        fileExtensionList = tuple(fileExtensions)
        _loader_registry.append(RegisteredLoader(formatName, fileExtensionList, cls))
        return cls

    return decorator


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
        self.thread_pool = QThreadPool()  # Global thread pool
        self.active_loading_processes = []  # Track active processes
        self.load_timeout_ms = 120000  # Increase timeout to 120 seconds (2 minutes)
        self.large_file_threshold_mb = 100  # larger files will use an extended timeout
        self.largeFileTimeoutMs = 600000  # 10 minutes for very large files

    # public methods
    def _get_file_size(self, filePath):
        """Get file size in megabytes"""
        try:
            return os.path.getsize(filePath) / (1024 * 1024)  # Convert to MB
        except:
            return 0

    def load_image_data(
        self, file_path=None, on_success_callback=None, on_failure_callback=None
    ):
        """Loads a new image and adds it to the project.

        If filePath is None, prompts the user to select a file using a file dialog.
        Calls onSuccessCallback after the image is loaded.
        onSuccessCallback should accept two arguments: the array of raster data, and a Metadata Object.

        Args:
            file_path: Path to the image file. If None, prompts user to select a file.
            on_success_callback: Function to call on successful load, receives image entity with raster and metadata.
            on_failure_callback: Function to call on load failure, receives error message.

        Returns:
            (raster, metadata): Data from the image file, or None if loading fails
        """
        logger.debug(f"Loading image data for {file_path}")
        if file_path is None:
            file_path = self._request_file_path()
            if file_path is None:
                # if user closed file dialog without selecting a file.
                logger.info("No file path provided.")
                return

        # Check file size and adjust timeout
        file_size_mb = self._get_file_size(file_path)
        timeout_ms = self.load_timeout_ms
        progress_dialog = None

        if file_size_mb > self.large_file_threshold_mb:
            timeout_ms = self.largeFileTimeoutMs
            logger.info(
                f"Large file detected ({file_size_mb:.2f} MB), using extended timeout"
            )

            # Show progress dialog for large files
            progress_dialog = self._show_large_file_loading_dialog(file_path, timeout_ms)
        try:
            loader = self._get_loader(file_path)

            # Wrap the callbacks to handle the progress dialog
            original_success = on_success_callback
            original_failure = on_failure_callback

            def success_with_dialog(raster, metadata):
                if progress_dialog:
                    progress_dialog.close()
                if original_success:
                    image = Image(raster, metadata)
                    original_success(image)

            def failure_with_dialog(error_msg):
                if progress_dialog:
                    progress_dialog.close()
                if original_failure:
                    original_failure(error_msg)
                else:
                    self._show_error_message(error_msg)

            self._create_new_load_process(
                loader, file_path, success_with_dialog, failure_with_dialog, timeout_ms
            )
            if progress_dialog:
                progress_dialog.exec()  # Show the progress dialog and wait for it to finish

        except ValueError as e:
            if progress_dialog:
                progress_dialog.close()
            logger.error(f"Error loading image: {e}")
            if on_failure_callback:
                on_failure_callback(str(e))
            else:
                self._show_error_message(f"Error loading image: {e}")

    def load_metadata_only(
        self, file_path, on_success_callback=None, on_failure_callback=None
    ):
        """
        Load only the metadata for an image file without loading the full raster data.

        This is useful for very large files where we want to inspect the metadata before
        deciding whether to load the full file.

        Args:
            file_path: Path to the image file
            on_success_callback: Function to call on successful load, receives (metadata)
            on_failure_callback: Function to call on load failure, receives error message
        """
        if file_path is None:
            file_path = self._request_file_path()
            if file_path is None:
                return

        try:
            loader = self._get_loader(file_path)

            # Create a small temporary array just to satisfy the metadata loader
            temp_array = np.zeros((1, 1, 3), dtype=np.uint8)

            # Load metadata
            try:
                metadata = loader.loadMetadata(temp_array, file_path)
                if on_success_callback:
                    on_success_callback(metadata)
            except Exception as e:
                logger.error(f"Error loading metadata: {e}")
                if on_failure_callback:
                    on_failure_callback(f"Error loading metadata: {e}")
                else:
                    self._show_error_message(f"Error loading metadata: {e}")

        except ValueError as e:
            logger.error(f"Error finding loader: {e}")
            if on_failure_callback:
                on_failure_callback(str(e))
            else:
                self._show_error_message(f"Error loading image: {e}")

    @staticmethod
    def get_image_type_filter():
        """Returns a list of file filters for the image file dialog."""
        filters = "Image File ("
        for loader in _loader_registry:
            for extension in loader.fileExtensions:
                filters += f"*{extension} "
        filters = filters.strip() + ")"
        return filters

    # private methods
    def _show_large_file_options_dialog(self, filePath, file_size_mb):
        """
        Show a dialog with options for loading a large file

        Returns:
            str: One of 'full', 'preview', 'metadata', or 'cancel'
        """
        dialog = QDialog(QApplication.activeWindow())
        dialog.setWindowTitle("Large File Detected")

        layout = QVBoxLayout()

        # Add explanation
        layout.addWidget(
            QLabel(
                f"The file you're trying to load is very large ({file_size_mb:.1f} MB).\n"
                "Loading large files may take a long time and use significant memory."
            )
        )

        # Add options
        option_group = QButtonGroup(dialog)

        preview_option = QRadioButton("Load a downsampled preview (faster, less memory)")
        preview_option.setChecked(True)
        option_group.addButton(preview_option)
        layout.addWidget(preview_option)

        full_option = QRadioButton("Load the full file (slow, high memory usage)")
        option_group.addButton(full_option)
        layout.addWidget(full_option)

        metadata_option = QRadioButton("Load metadata only (fastest)")
        option_group.addButton(metadata_option)
        layout.addWidget(metadata_option)

        # Add buttons
        button_layout = QHBoxLayout()
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(dialog.reject)

        load_button = QPushButton("Load")
        load_button.clicked.connect(dialog.accept)

        button_layout.addWidget(cancel_button)
        button_layout.addWidget(load_button)

        layout.addLayout(button_layout)
        dialog.setLayout(layout)

        # Show dialog and get result
        result = dialog.exec()

        if result == QDialog.DialogCode.Accepted:
            if preview_option.isChecked():
                return "preview"
            elif full_option.isChecked():
                return "full"
            elif metadata_option.isChecked():
                return "metadata"

        return "cancel"

    def _create_new_load_process(
        self, loader, filePath, onSuccessCallback, onFailureCallback, timeout_ms=None
    ):
        """Creates and starts a new image loading process in the thread pool."""
        logger.info(f"Creating new image loading process for {filePath}")
        process = self.ImageLoadProcess(
            loader, filePath, onSuccessCallback, onFailureCallback
        )
        process.signals.sigFinished.connect(self._on_loading_process_finished)

        # Set up a timeout for the loading process
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self._handle_load_timeout(process))

        # Use custom timeout if provided, otherwise use the default
        if timeout_ms is None:
            timeout_ms = self.load_timeout_ms

        timer.start(timeout_ms)
        process.timer = timer

        self.active_loading_processes.append(process)
        self.thread_pool.start(process)

    def _handle_load_timeout(self, process):
        """Handle a loading process timeout."""
        if process in self.active_loading_processes:
            logger.error(f"Image loading timeout for {process.filePath}")
            self.active_loading_processes.remove(process)
            if process.onFailureCallback:
                process.onFailureCallback(
                    "Loading timed out. The file may be too large or corrupted."
                )
            else:
                self._show_error_message(
                    f"Loading timed out for {process.filePath}. The file may be too large or corrupted."
                )

    def _on_loading_process_finished(self, loadingProcess):
        """Handles cleanup and callback (if success) once the image is loaded."""
        # Cancel the timeout timer
        if hasattr(loadingProcess, "timer") and loadingProcess.timer.isActive():
            loadingProcess.timer.stop()

        if loadingProcess in self.active_loading_processes:
            self.active_loading_processes.remove(loadingProcess)  # Cleanup

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
                    self._show_warning_message(
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
                    self._show_error_message(f"Failed to load image: {error_msg}")

    def _show_large_file_loading_dialog(self, filePath, timeout_ms):
        """Show a dialog with progress information for large files"""
        logger.info(f"Showing large file loading dialog for {filePath}")
        file_name = os.path.basename(filePath)
        file_size_mb = self._get_file_size(filePath)

        dialog = QProgressDialog(
            f"Loading large file ({file_size_mb:.1f} MB)...\n{file_name}",
            "Cancel",
            0,
            100,
            QApplication.activeWindow(),
        )
        dialog.setWindowTitle("Loading Large File")
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        dialog.setMinimumDuration(1000)  # Show after 1 second
        dialog.setAutoClose(True)
        dialog.setAutoReset(True)

        # Make the progress bar pulse for indeterminate progress
        dialog.setMinimum(0)
        dialog.setMaximum(0)

        # Set the timeout
        estimated_seconds = timeout_ms / 1000
        dialog.setLabelText(
            f"Loading large file ({file_size_mb:.1f} MB)...\n"
            f"{file_name}\n\n"
            f"This may take up to {estimated_seconds:.0f} seconds for large files."
        )
        return dialog

    def _show_error_message(self, message):
        """Display an error message to the user."""
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setWindowTitle("Error Loading Image")
        msg_box.setText(message)
        msg_box.exec()

    def _show_warning_message(self, message):
        """Display a warning message to the user."""
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setWindowTitle("Image Loaded with Warnings")
        msg_box.setText(message)
        msg_box.exec()

    def load_image_sync(self, file_path=None):
        """
        Load an image synchronously and return the result.

        This is a convenience method for simple cases where async loading isn't needed. Will block until complete.

        Args:
            file_path: Path to the image file

        Returns:
            Image entity on success, or None on failure
        """
        result = None
        isComplete = False

        def on_success(raster, metadata):
            nonlocal result
            nonlocal isComplete

            result = Image(raster, metadata)
            isComplete = True

        def on_failure(error_msg):
            logger.error(f"Sync loading failed: {error_msg}")

        self.load_image_data(file_path, on_success, on_failure)

        # Wait until loading is complete (not ideal for large files, but works for simple cases)
        import time

        timeout = time.time() + self.load_timeout_ms / 1000
        while not isComplete and time.time() < timeout:
            time.sleep(0.1)

        return result

    # private helpers
    @staticmethod
    def _request_file_path():
        """Opens a file dialog to request an image file path from the user."""
        file_name, _ = QFileDialog.getOpenFileName(
            None,
            "Open File",
            "",
            ImageLoadingService.get_image_type_filter(),
        )
        return file_name if file_name else None

    @staticmethod
    def _get_loader(filePath):
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
        for loader in _loader_registry:
            if file_extension in loader.fileExtensions:
                return loader.loaderClass()
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
        for loader in _loader_registry:
            try:
                # Just try to read a tiny bit to see if it works
                test_mode = getattr(loader.loaderClass, "supports_preview", False)
                if test_mode:
                    loader.loaderClass.loadRasterData(filePath, loadingMode="preview")
                    return loader.loaderClass()
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
