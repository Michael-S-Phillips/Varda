# standard library
import os
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

from .data_sources import DataSource, RasterioDataSource, InMemoryDataSource
from .data_sources.registry import datasource_registry, get_image_type_filter
from .varda_raster import VardaRaster

logger = logging.getLogger(__name__)


def openDataSource(filePath: str) -> DataSource:
    """Open a DataSource for the given file path.

    Uses extension-based dispatch from the registry. Falls back to
    RasterioDataSource for unregistered extensions (supports any GDAL format).
    """
    ext = Path(filePath).suffix.lower()

    # Find a registered DataSource for this extension
    for entry in datasource_registry:
        if ext in entry.fileExtensions:
            return entry.dataSourceClass(filePath)

    # Default: try RasterioDataSource (supports any GDAL format)

    return RasterioDataSource(filePath)


class ImageLoadingService:
    """Handles image loading in a background thread using QThreadPool.

    Uses the DataSource system to open files and wraps them in VardaRaster entities.
    """

    class LoadStatus(Enum):
        LOAD = 0
        SUCCESS = 1
        FAIL = 2
        WARNING = 3

    def __init__(self):
        self.thread_pool = QThreadPool()
        self.active_loading_processes = []
        self.load_timeout_ms = 120000  # 2 minutes
        self.large_file_threshold_mb = 100
        self.largeFileTimeoutMs = 600000  # 10 minutes

    # public methods
    def _get_file_size(self, filePath):
        """Get file size in megabytes"""
        try:
            return os.path.getsize(filePath) / (1024 * 1024)
        except Exception:
            return 0

    def load_image_data(
        self, file_path=None, on_success_callback=None, on_failure_callback=None
    ):
        """Load a new image as a VardaRaster.

        If file_path is None, prompts the user to select a file.
        on_success_callback receives a VardaRaster on success.
        on_failure_callback receives an error message string on failure.
        """
        logger.debug(f"Loading image data for {file_path}")
        if file_path is None:
            file_path = self._request_file_path()
            if file_path is None:
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
            progress_dialog = self._show_large_file_loading_dialog(
                file_path, timeout_ms
            )

        try:
            original_success = on_success_callback
            original_failure = on_failure_callback

            def success_with_dialog(vardaRaster):
                if progress_dialog:
                    progress_dialog.close()
                if original_success:
                    original_success(vardaRaster)

            def failure_with_dialog(error_msg):
                if progress_dialog:
                    progress_dialog.close()
                if original_failure:
                    original_failure(error_msg)
                else:
                    self._show_error_message(error_msg)

            self._create_new_load_process(
                file_path, success_with_dialog, failure_with_dialog, timeout_ms
            )
            if progress_dialog:
                progress_dialog.exec()

        except Exception as e:
            if progress_dialog:
                progress_dialog.close()
            logger.error(f"Error loading image: {e}")
            if on_failure_callback:
                on_failure_callback(str(e))
            else:
                self._show_error_message(f"Error loading image: {e}")

    # private methods
    def _show_large_file_options_dialog(self, filePath, file_size_mb):
        """Show a dialog with options for loading a large file."""
        dialog = QDialog(QApplication.activeWindow())
        dialog.setWindowTitle("Large File Detected")

        layout = QVBoxLayout()
        layout.addWidget(
            QLabel(
                f"The file you're trying to load is very large ({file_size_mb:.1f} MB).\n"
                "Loading large files may take a long time and use significant memory."
            )
        )

        option_group = QButtonGroup(dialog)

        preview_option = QRadioButton(
            "Load a downsampled preview (faster, less memory)"
        )
        preview_option.setChecked(True)
        option_group.addButton(preview_option)
        layout.addWidget(preview_option)

        full_option = QRadioButton("Load the full file (slow, high memory usage)")
        option_group.addButton(full_option)
        layout.addWidget(full_option)

        metadata_option = QRadioButton("Load metadata only (fastest)")
        option_group.addButton(metadata_option)
        layout.addWidget(metadata_option)

        button_layout = QHBoxLayout()
        cancel_button = QPushButton("Cancel")
        cancel_button.clicked.connect(dialog.reject)
        load_button = QPushButton("Load")
        load_button.clicked.connect(dialog.accept)
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(load_button)

        layout.addLayout(button_layout)
        dialog.setLayout(layout)

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
        self, filePath, onSuccessCallback, onFailureCallback, timeout_ms=None
    ):
        """Creates and starts a new image loading process in the thread pool."""
        logger.info(f"Creating new image loading process for {filePath}")
        process = self.ImageLoadProcess(filePath, onSuccessCallback, onFailureCallback)
        process.signals.sigFinished.connect(self._on_loading_process_finished)

        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self._handle_load_timeout(process))

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
        """Handles cleanup and callback once the image is loaded."""
        if hasattr(loadingProcess, "timer") and loadingProcess.timer.isActive():
            loadingProcess.timer.stop()

        if loadingProcess in self.active_loading_processes:
            self.active_loading_processes.remove(loadingProcess)

            if loadingProcess.status == ImageLoadingService.LoadStatus.SUCCESS:
                vardaRaster = loadingProcess.result
                logger.info(f"Done loading image: {vardaRaster.filePath}")

                if loadingProcess.onSuccessCallback:
                    loadingProcess.onSuccessCallback(vardaRaster)

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
        """Show a dialog with progress information for large files."""
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
        dialog.setMinimumDuration(1000)
        dialog.setAutoClose(True)
        dialog.setAutoReset(True)
        dialog.setMinimum(0)
        dialog.setMaximum(0)

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
        """Load an image synchronously. Blocks until complete.

        Returns:
            VardaRaster on success, or None on failure.
        """
        result = None
        isComplete = False

        def on_success(vardaRaster):
            nonlocal result, isComplete
            result = vardaRaster
            isComplete = True

        def on_failure(error_msg):
            nonlocal isComplete
            logger.error(f"Sync loading failed: {error_msg}")
            isComplete = True

        self.load_image_data(file_path, on_success, on_failure)

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
            get_image_type_filter(),
        )
        return file_name if file_name else None

    class ImageLoadProcess(QRunnable):
        """Represents a single image loading process running in a thread.

        Opens a DataSource, reads all bands into memory, and wraps in VardaRaster.
        """

        class Signals(QObject):
            sigFinished: pyqtSignal = pyqtSignal(object)

        def __init__(self, filePath, onSuccessCallback, onFailureCallback):
            super().__init__()
            self.filePath = filePath
            self.onSuccessCallback = onSuccessCallback
            self.onFailureCallback = onFailureCallback
            self.signals = self.Signals()
            self.result = None
            self.error = None
            self.status = ImageLoadingService.LoadStatus.LOAD

        def run(self):
            """Load the image from a separate thread."""
            logger.info(f"Loading image: {self.filePath}")
            try:
                # get handler for file
                ds = openDataSource(self.filePath)

                # Wrap in InMemoryDataSource, so that it is just as fast as it was before
                # later we'll want the user to be able to choose whether to do this.
                memDs = InMemoryDataSource(ds)

                # Create VardaRaster
                self.result = VardaRaster.fromDataSource(memDs)

                self.status = ImageLoadingService.LoadStatus.SUCCESS
                logger.info(f"Image loading success: {self.filePath}")

            except Exception as e:
                self.status = ImageLoadingService.LoadStatus.FAIL
                self.error = e
                logger.error(f"Image loading failed: {str(e)}")
                logger.error(traceback.format_exc())
            finally:
                self.signals.sigFinished.emit(self)
