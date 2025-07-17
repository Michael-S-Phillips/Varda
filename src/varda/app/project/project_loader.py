"""
Module for loading Project entities with their associated image data.
"""

import logging
from pathlib import Path
from typing import Callable, Optional, Tuple

from PyQt6.QtWidgets import QFileDialog, QMessageBox

from varda.app.project.project_io import ProjectIO
from varda.app.image import ImageLoadingService
from varda.core.entities import Project, Image, Metadata
from varda.gui.widgets import FileInputDialog

logger = logging.getLogger(__name__)


class ProjectLoader:
    """
    Service for loading Project entities with their associated image data.

    This class is responsible for:
    1. Loading and saving Project entities using ProjectIO
    2. Loading the raster data for images in a Project using ImageLoadingService
    3. Handling missing image files by prompting the user for updated paths
    """

    def __init__(
        self,
        image_loading_service: Optional[ImageLoadingService] = None,
        io: Optional[ProjectIO] = None,
    ):
        """
        Initialize the ProjectLoader with optional services.

        Args:
            image_loading_service: The service to use for loading image data.
                                  If None, a new instance will be created.
            io: The ProjectIO implementation to use for loading/saving projects.
                If None, the caller must provide an IO when calling load/save methods.
        """
        self._image_loading_service = image_loading_service or ImageLoadingService()
        self._io = io

    def loadProjectImages(
        self, project: Project, on_complete_callback: Optional[Callable] = None
    ) -> None:
        """
        Load the raster data for all images in the project.

        Args:
            project: The Project entity to load images for.
            on_complete_callback: Optional callback to call when all images are loaded.
        """
        # Track completed loads to call the callback when all images are loaded
        expected_loads = len(project.images)
        completed_loads = 0

        if expected_loads == 0:
            logger.info("No images to load in project")
            if on_complete_callback:
                on_complete_callback()
            return

        def on_image_loaded(raster, metadata, image_index):
            """Callback for when an individual image finishes loading."""
            nonlocal completed_loads

            # Update the image with the loaded raster data
            project.images[image_index].raster = raster
            completed_loads += 1
            logger.info(f"Loaded image {completed_loads}/{expected_loads} for project")

            # If this is the last image, call the completion callback
            if completed_loads == expected_loads:
                logger.info("All images loaded successfully for project")
                if on_complete_callback:
                    on_complete_callback()

        # Load each image
        for i, image in enumerate(project.images):
            # Check if the image file exists
            file_path = Path(image.metadata.filePath)
            if not file_path.exists():
                logger.warning(f"Image file {file_path} does not exist")
                # Handle missing files (could prompt user for new path here)
                # For now, just skip this image
                expected_loads -= 1
                continue

            # Create callback with captured variables for this iteration
            self._image_loading_service.loadImageData(
                str(file_path),
                lambda raster, metadata, idx=i: on_image_loaded(raster, metadata, idx),
            )

        # If no images to load (all were skipped), call the callback immediately
        if expected_loads == 0:
            logger.info("No valid images to load in project")
            if on_complete_callback:
                on_complete_callback()

    def load_project_with_images(
        self, project: Project, on_complete_callback: Optional[Callable] = None
    ) -> None:
        """
        Load the raster data for all images in the project.

        This is a convenience method that calls load_project_images.

        Args:
            project: The Project entity to load images for.
            on_complete_callback: Optional callback to call when all images are loaded.
        """
        self.loadProjectImages(project, on_complete_callback)

    def handle_missing_image_files(self, project: Project) -> Project:
        """
        Handle missing image files by prompting the user for updated paths.

        Args:
            project: The Project entity to check for missing image files.

        Returns:
            Project: The updated Project entity with resolved image paths.
        """
        # Handle missing image files by prompting the user for updated paths
        for image in project.images:
            oldPath = Path(image.metadata.filePath)
            if not oldPath.exists():
                logger.warning(f"Image {oldPath} does not exist!")
                newPath = Path(
                    FileInputDialog.getFilePath(
                        f"Cannot find {oldPath}. Please locate this image.",
                        fileFilter=f"Image File ({oldPath.name})",
                    )
                )

                if newPath.name == oldPath.name:
                    image.metadata.filePath = str(newPath)
                else:
                    logger.info(f"Skipping image {oldPath}")
                    # Mark for removal (we'll filter these out later)
                    image.metadata.filePath = ""

        # Remove images with empty file paths (skipped during path resolution)
        project.images = [img for img in project.images if img.metadata.filePath != ""]

        return project

    def load_project(
        self, io: Optional[ProjectIO] = None, loadPath: Optional[str] = None
    ) -> Tuple[bool, Optional[Project]]:
        """
        Load a project from a file.

        Args:
            io: The ProjectIO implementation to use. If None, uses the one provided at initialization.
            loadPath: Optional path to load the project from. If None, prompts the user to select a file.

        Returns:
            Tuple[bool, Optional[Project]]: Success status and the loaded Project entity.
        """
        # Use the provided IO or the one from initialization
        io = io or self._io
        if io is None:
            logger.error("No I/O module available. Cannot load project.")
            return False, None

        # If no path provided, prompt for one
        if loadPath is None:
            f, _ = QFileDialog.getOpenFileName(
                None, "Open File", "", "Varda project file (*.varda)"
            )
            if not f:
                return False, None
            loadPath = f

        # Attempt to load the project data
        success, project = io.load(Path(loadPath))
        if not success:
            QMessageBox.critical(
                None, "Error", f"Failed to load project from {loadPath}!"
            )
            logger.error(f"Failed to load project from {loadPath}")
            return False, None

        # Handle missing image files
        project = self.handle_missing_image_files(project)

        return True, project

    def save_project(
        self, project: Project, io: Optional[ProjectIO] = None, saveAs: bool = False
    ) -> Tuple[bool, Optional[Path]]:
        """
        Save a project to a file.

        Args:
            project: The Project entity to save.
            io: The ProjectIO implementation to use. If None, uses the one provided at initialization.
            saveAs: If True, prompt for a new file path regardless of current project.

        Returns:
            Tuple[bool, Optional[Path]]: Success status and the path where the project was saved.
        """
        # Use the provided IO or the one from initialization
        io = io or self._io
        if io is None:
            logger.error("No I/O module available. Cannot save project.")
            return False, None

        # If we need to prompt for a path
        if project.path is None or saveAs is True:
            fileName = QFileDialog.getSaveFileName(
                None, "Save File", "../", "Varda project file (*.varda)"
            )
            if fileName[0]:
                # set the path for the project.
                project.path = Path(fileName[0])
            else:
                return False, None

        # Serialize and save the data
        success = io.save(project)
        if not success:
            QMessageBox.critical(None, "Error", "Failed to save project!")
            logger.error(f"Failed to save project to {project.path}")
            return False, None

        logger.info(f"Project saved to {project.path}")
        return True, project.path
