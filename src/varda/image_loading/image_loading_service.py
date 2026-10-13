import ctypes
import logging
import os
import sys
import traceback
from enum import Enum
from pathlib import Path

import numpy as np

from PyQt6.QtCore import Qt, pyqtSignal, QObject, QThreadPool, QRunnable, QTimer
from PyQt6.QtWidgets import (
    QFileDialog,
    QMessageBox,
    QApplication,
)

from .data_sources import DataSource, RasterioDataSource, InMemoryDataSource
from .data_sources.cached_data_source import CachedDataSource
from .data_sources.registry import datasource_registry, get_image_type_filter
from varda.branding.loader import BusyDialog
from varda.common.entities import VardaRaster

logger = logging.getLogger(__name__)


def openDataSource(filePath: str) -> DataSource:
    """Open a DataSource for the given file path.

    The first registered source whose extensions match and whose ``canOpen``
    (if it has one) accepts the file opens it; e.g. an ``.img`` is ENVI only
    with a header beside it. Otherwise RasterioDataSource (any GDAL format).
    """
    ext = Path(filePath).suffix.lower()
    for entry in datasource_registry:
        if ext not in entry.fileExtensions:
            continue
        canOpen = getattr(entry.dataSourceClass, "canOpen", None)
        if canOpen is None or canOpen(filePath):
            return entry.dataSourceClass(filePath)

    # Default: try RasterioDataSource (supports any GDAL format)

    return RasterioDataSource(filePath)


def physicalMemoryBytes() -> int:
    """Installed RAM, or 8 GiB if it can't be read."""
    try:
        return int(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"))
    except (AttributeError, ValueError, OSError):
        pass
    if sys.platform == "win32":
        status = _MemoryStatus()
        status.dwLength = ctypes.sizeof(_MemoryStatus)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):  # ty: ignore[unresolved-attribute]
            return int(status.ullTotalPhys)
    return 8 * 1024**3


class _MemoryStatus(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


IN_MEMORY_SHARE = 0.25  # of installed RAM: images larger than this read on demand


def wrapForReading(source: DataSource, limitBytes: int | None = None) -> DataSource:
    """Load ``source`` into memory if it fits within ``limitBytes`` (a quarter
    of RAM by default; float32 once no-data is filled), otherwise read it on
    demand through a small cache, so opening a very large cube is quick and
    doesn't exhaust memory."""
    limit = (
        int(physicalMemoryBytes() * IN_MEMORY_SHARE)
        if limitBytes is None
        else limitBytes
    )
    size = (
        source.width
        * source.height
        * source.bandCount
        * max(np.dtype(source.dtype).itemsize, 4)
    )
    if size <= limit:
        return InMemoryDataSource(source)
    logger.info(
        "Reading %s on demand (%.1f GB is more than %.1f GB)",
        source.filePath or "image",
        size / 1e9,
        limit / 1e9,
    )
    return CachedDataSource(source)


class ImageLoadingService:
    """Handles image loading in a background thread using QThreadPool.

    Uses the DataSource system to open files and wraps them in VardaRaster entities.
    """

    active_loading_processes: list = []
    LOAD_TIMEOUT_MS = 120000  # 2 minutes
    LARGE_FILE_THRESHOLD_MB = 100
    LARGE_FILE_TIMEOUT_MS = 600000  # 10 minutes

    class LoadStatus(Enum):
        LOAD = 0
        SUCCESS = 1
        FAIL = 2
        WARNING = 3

    @classmethod
    def load_image_data(
        cls, file_path=None, on_success_callback=None, on_failure_callback=None
    ):
        """Load a new image as a VardaRaster.

        If file_path is None, prompts the user to select a file.
        on_success_callback receives a VardaRaster on success.
        on_failure_callback receives an error message string on failure.
        """
        logger.debug(f"Loading image data for {file_path}")
        if file_path is None:
            file_path = cls._request_file_path()
            if file_path is None:
                logger.info("No file path provided.")
                return

        # Check file size and adjust timeout
        file_size_mb = cls._get_file_size(file_path)
        timeout_ms = cls.LOAD_TIMEOUT_MS
        progress_dialog = None

        if file_size_mb > cls.LARGE_FILE_THRESHOLD_MB:
            timeout_ms = cls.LARGE_FILE_TIMEOUT_MS
            logger.info(
                f"Large file detected ({file_size_mb:.2f} MB), using extended timeout"
            )
            progress_dialog = cls._show_large_file_loading_dialog(file_path, timeout_ms)

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
                    cls._show_error_message(error_msg)

            cls._create_new_load_process(
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
                cls._show_error_message(f"Error loading image: {e}")

    @classmethod
    def _get_file_size(cls, filePath):
        """Get file size in megabytes"""
        try:
            return Path(filePath).stat().st_size / (1024 * 1024)
        except OSError:
            return 0

    @classmethod
    def _create_new_load_process(
        cls, filePath, onSuccessCallback, onFailureCallback, timeout_ms=None
    ):
        """Creates and starts a new image loading process in the thread pool."""
        logger.info(f"Creating new image loading process for {filePath}")
        process = cls.ImageLoadProcess(filePath, onSuccessCallback, onFailureCallback)
        process.signals.sigFinished.connect(cls._on_loading_process_finished)

        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: cls._handle_load_timeout(process))

        if timeout_ms is None:
            timeout_ms = cls.LOAD_TIMEOUT_MS

        timer.start(timeout_ms)
        process.timer = timer

        cls.active_loading_processes.append(process)
        QThreadPool.globalInstance().start(process)

    @classmethod
    def _handle_load_timeout(cls, process):
        """Handle a loading process timeout."""
        if process in cls.active_loading_processes:
            logger.error(f"Image loading timeout for {process.filePath}")
            cls.active_loading_processes.remove(process)
            if process.onFailureCallback:
                process.onFailureCallback(
                    "Loading timed out. The file may be too large or corrupted."
                )
            else:
                cls._show_error_message(
                    f"Loading timed out for {process.filePath}. The file may be too large or corrupted."
                )

    @classmethod
    def _on_loading_process_finished(cls, loadingProcess):
        """Handles cleanup and callback once the image is loaded."""
        if hasattr(loadingProcess, "timer") and loadingProcess.timer.isActive():
            loadingProcess.timer.stop()

        if loadingProcess in cls.active_loading_processes:
            cls.active_loading_processes.remove(loadingProcess)

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
                    cls._show_error_message(f"Failed to load image: {error_msg}")

    @classmethod
    def _show_large_file_loading_dialog(cls, filePath, timeout_ms):
        """Show a dialog with progress information for large files."""
        logger.info(f"Showing large file loading dialog for {filePath}")
        file_name = Path(filePath).name
        file_size_mb = cls._get_file_size(filePath)

        estimated_seconds = timeout_ms / 1000
        dialog = BusyDialog(
            f"Loading large file ({file_size_mb:.1f} MB)…\n"
            f"{file_name}\n\n"
            f"This may take up to {estimated_seconds:.0f} seconds for large files.",
            title="Loading Large File",
            parent=QApplication.activeWindow(),
        )
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        dialog.showAfter(1000)
        return dialog

    @classmethod
    def _show_error_message(cls, message):
        """Display an error message to the user."""
        msg_box = QMessageBox()
        msg_box.setIcon(QMessageBox.Icon.Critical)
        msg_box.setWindowTitle("Error Loading Image")
        msg_box.setText(message)
        msg_box.exec()

    @classmethod
    def load_images(
        cls, file_paths=None, on_success_callback=None, on_failure_callback=None
    ):
        """Load one or more images.

        If file_paths is None, prompts the user to select one or more files.
        Each file is loaded independently in its own background process, so the
        callbacks are invoked once per file (on_success_callback receives a
        VardaRaster, on_failure_callback receives an error message string).
        """
        if file_paths is None:
            file_paths = cls._request_file_paths()
            if not file_paths:
                logger.info("No file paths provided.")
                return

        for file_path in file_paths:
            cls.load_image_data(
                file_path=file_path,
                on_success_callback=on_success_callback,
                on_failure_callback=on_failure_callback,
            )

    @classmethod
    def load_image_sync(cls, file_path=None):
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

        cls.load_image_data(file_path, on_success, on_failure)

        import time

        timeout = time.time() + cls.LOAD_TIMEOUT_MS / 1000
        while not isComplete and time.time() < timeout:
            time.sleep(0.1)

        return result

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

    @staticmethod
    def _request_file_paths():
        """Opens a file dialog to request one or more image file paths."""
        file_names, _ = QFileDialog.getOpenFileNames(
            None,
            "Open File(s)",
            "",
            get_image_type_filter(),
        )
        return file_names if file_names else None

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

                # In memory when it fits comfortably, else read on demand
                self.result = VardaRaster.fromDataSource(wrapForReading(ds))

                self.status = ImageLoadingService.LoadStatus.SUCCESS
                logger.info(f"Image loading success: {self.filePath}")

            except Exception as e:
                self.status = ImageLoadingService.LoadStatus.FAIL
                self.error = e
                logger.error(f"Image loading failed: {str(e)}")
                logger.error(traceback.format_exc())
            finally:
                self.signals.sigFinished.emit(self)
