"""
Handles loading project data, including image raster data.

This module provides classes for loading project data from disk, including
the raster data for images, which is loaded separately from the project metadata.
"""

import logging
from pathlib import Path
from typing import Callable, Optional, Tuple

from PyQt6.QtWidgets import QFileDialog, QMessageBox

from varda.common.domain import Project
from varda._test_project_module_thing.infrastructure.project_io import ProjectIO

logger = logging.getLogger(__name__)


class ProjectLoader:
    """
    Handles loading and saving project data, including image raster data.
    """

    def __init__(self, image_loading_service=None, io: Optional[ProjectIO] = None):
        """
        Initialize the project loader.

        Args:
            image_loading_service: Service for loading image data.
            io: Optional project I/O handler. If None, a new one will be created.
        """
        self._image_loading_service = image_loading_service
        self._io = io

    def load_project_images(
        self, project: Project, on_complete_callback: Optional[Callable] = None
    ):
        """
        Load the raster data for all images in a project.

        Args:
            project: The project containing the images to load.
            on_complete_callback: Optional callback to call when all images are loaded.
        """
        if not project.images:
            if on_complete_callback:
                on_complete_callback()
            return

        # Count of images that still need to be loaded
        remaining_images = len(project.images)

        # Callback for when an image is loaded
        def on_image_loaded(raster, metadata, image_index):
            nonlocal remaining_images

            # Update the image with the loaded raster data
            project.images[image_index].raster = raster

            # Decrement the count of remaining images
            remaining_images -= 1

            # If all images are loaded, call the completion callback
            if remaining_images == 0 and on_complete_callback:
                on_complete_callback()

        # Load each image
        for i, image in enumerate(project.images):
            # Check if the image file exists
            if image.metadata.filePath and Path(image.metadata.filePath).exists():
                # Load the image data
                self._image_loading_service.loadImageData(
                    image.metadata.filePath,
                    lambda raster, metadata, idx=i: on_image_loaded(
                        raster, metadata, idx
                    ),
                )
            else:
                # Handle missing image file
                logger.warning(f"Image file not found: {image.metadata.filePath}")
                remaining_images -= 1

                # If all images are loaded (or failed), call the completion callback
                if remaining_images == 0 and on_complete_callback:
                    on_complete_callback()

    def load_project_with_images(
        self, project: Project, on_complete_callback: Optional[Callable] = None
    ):
        """
        Load a project and its images.

        Args:
            project: The project to load.
            on_complete_callback: Optional callback to call when the project is loaded.
        """
        # Handle missing image files
        self.handle_missing_image_files(project)

        # Load the image data
        self.load_project_images(project, on_complete_callback)

    def handle_missing_image_files(self, project: Project):
        """
        Handle missing image files in a project.

        Args:
            project: The project to check for missing image files.
        """
        missing_files = []

        # Check each image for missing files
        for image in project.images:
            if image.metadata.filePath and not Path(image.metadata.filePath).exists():
                missing_files.append(image.metadata.filePath)

        # If there are missing files, show a warning
        if missing_files:
            message = "The following image files could not be found:\n\n"
            message += "\n".join(missing_files[:5])

            if len(missing_files) > 5:
                message += f"\n... and {len(missing_files) - 5} more"

            message += "\n\nThese images will not be loaded."

            QMessageBox.warning(None, "Missing Image Files", message)

    def load_project(
        self, io: Optional[ProjectIO] = None, load_path: Optional[Path] = None
    ) -> Tuple[bool, Optional[Project]]:
        """
        Load a project from a file.

        Args:
            io: Optional project I/O handler. If None, uses the one provided at initialization.
            load_path: Optional path to the project file. If None, prompts the user to select a file.

        Returns:
            Tuple[bool, Optional[Project]]: Success status and the loaded project.
        """
        # Use the provided I/O handler or the one from initialization
        io = io or self._io

        if io is None:
            logger.error("No ProjectIO handler provided.")
            return False, None

        # If no path is provided, prompt the user to select a file
        if load_path is None:
            file_dialog = QFileDialog()
            file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
            file_dialog.setNameFilter("Varda Project Files (*.varda)")

            if file_dialog.exec():
                load_path = Path(file_dialog.selectedFiles()[0])
            else:
                return False, None

        # Load the project data
        success, project = io.load(load_path)

        if not success:
            return False, None

        return True, project

    def save_project(
        self, project: Project, io: Optional[ProjectIO] = None, save_as: bool = False
    ) -> Tuple[bool, Optional[Path]]:
        """
        Save a project to a file.

        Args:
            project: The project to save.
            io: Optional project I/O handler. If None, uses the one provided at initialization.
            save_as: If True, prompts the user to select a file path.

        Returns:
            Tuple[bool, Optional[Path]]: Success status and the path where the project was saved.
        """
        # Use the provided I/O handler or the one from initialization
        io = io or self._io

        if io is None:
            logger.error("No ProjectIO handler provided.")
            return False, None

        # If save_as is True or the project has no path, prompt the user to select a file path
        if save_as or project.path is None:
            file_dialog = QFileDialog()
            file_dialog.setFileMode(QFileDialog.FileMode.AnyFile)
            file_dialog.setNameFilter("Varda Project Files (*.varda)")
            file_dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
            file_dialog.setDefaultSuffix("varda")

            if file_dialog.exec():
                project.path = Path(file_dialog.selectedFiles()[0])
            else:
                return False, None

        # Save the project data
        success = io.save(project)

        if not success:
            return False, None

        return True, project.path
