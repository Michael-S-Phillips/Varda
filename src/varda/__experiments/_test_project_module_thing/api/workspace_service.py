from typing import Protocol, Optional, List, Any
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal

from varda.common.domain import Image, Metadata, Band, Stretch, Plot, ROI


class WorkspaceChangeType:
    """Types of _test_project_module_thing data changes."""

    IMAGE = "image"
    BAND = "band"
    STRETCH = "stretch"
    METADATA = "metadata"
    PLOT = "plot"
    ROI = "roi"


class WorkspaceChangeModifier:
    """Modifiers for _test_project_module_thing data changes."""

    ADD = "add"
    REMOVE = "remove"
    UPDATE = "update"


class WorkspaceService(QObject):
    """
    Service for managing the _test_project_module_thing (project) data.

    This service provides methods for managing images, bands, stretches, and other
    project data. It uses PyQt signals to notify subscribers of changes to the data.
    """

    # Signal that emits when something changes in the _test_project_module_thing
    # Parameters: index, change_type, [change_modifier]
    sigDataChanged = pyqtSignal([int, str], [int, str, str])
    sigProjectChanged = pyqtSignal()

    def __init__(self, project_io):
        """
        Initialize the _test_project_module_thing service.

        Args:
            project_io: The project I/O handler for persistence.
        """
        super().__init__()
        self._project_io = project_io
        self._image_loading_service = None  # Will be set later
        self._roi_service = None  # Will be set later

    def set_image_loading_service(self, service):
        """Set the image loading service."""
        self._image_loading_service = service

    def set_roi_service(self, service):
        """Set the ROI service."""
        self._roi_service = service

    # Project operations
    def get_project_name(self) -> str:
        """Get the name of the current project."""
        return self._project_data.name

    def save_project(self, save_as: bool = False) -> bool:
        """
        Save the current project.

        Args:
            save_as: If True, prompt for a new file path.

        Returns:
            bool: True if the save was successful.
        """
        # Implementation details...
        return True

    def load_project(self, load_path: Optional[Path] = None) -> bool:
        """
        Load a project from a file.

        Args:
            load_path: Optional path to the project file.

        Returns:
            bool: True if the load was successful.
        """
        # Implementation details...
        return True

    # Image operations
    def get_image(self, index: int) -> Optional[Image]:
        """
        Get an image by index.

        Args:
            index: The index of the image.

        Returns:
            Image: The image at the specified index, or None if not found.
        """
        # Implementation details...
        return None

    def add_image(self, image: Image) -> int:
        """
        Add an image to the project.

        Args:
            image: The image to add.

        Returns:
            int: The index of the added image.
        """
        # Implementation details...
        return 0

    def load_new_image(self, path: Optional[Path] = None) -> Optional[int]:
        """
        Load a new image from a file.

        Args:
            path: Optional path to the image file.

        Returns:
            int: The index of the loaded image, or None if loading failed.
        """
        # Implementation details...
        return None

    def create_image(
        self,
        raster,
        metadata: Metadata,
        stretch: Optional[List[Stretch]] = None,
        band: Optional[List[Band]] = None,
        plot: Optional[List[Plot]] = None,
    ) -> int:
        """
        Create a new image with the given data.

        Args:
            raster: The image raster data.
            metadata: The image metadata.
            stretch: Optional list of stretch configurations.
            band: Optional list of band configurations.
            plot: Optional list of plots.

        Returns:
            int: The index of the created image.
        """
        # Implementation details...
        return 0

    def remove_image(self, index: int) -> None:
        """
        Remove an image from the project.

        Args:
            index: The index of the image to remove.
        """
        # Implementation details...

    def get_all_images(self) -> List[Image]:
        """
        Get all images in the project.

        Returns:
            List[Image]: A list of all images.
        """
        # Implementation details...
        return []

    # Metadata operations
    def update_metadata(self, index: int, key: str, value: Any) -> None:
        """
        Update a metadata field for an image.

        Args:
            index: The index of the image.
            key: The metadata key to update.
            value: The new value.
        """
        # Implementation details...

    # Stretch operations
    def add_stretch(self, index: int, stretch: Optional[Stretch] = None) -> int:
        """
        Add a stretch to an image.

        Args:
            index: The index of the image.
            stretch: Optional stretch configuration.

        Returns:
            int: The index of the added stretch.
        """
        # Implementation details...
        return 0

    def remove_stretch(self, index: int, stretch_index: int) -> None:
        """
        Remove a stretch from an image.

        Args:
            index: The index of the image.
            stretch_index: The index of the stretch to remove.
        """
        # Implementation details...

    def update_stretch(
        self,
        image_index: int,
        stretch_index: int,
        name: Optional[str] = None,
        min_r: Optional[float] = None,
        max_r: Optional[float] = None,
        min_g: Optional[float] = None,
        max_g: Optional[float] = None,
        min_b: Optional[float] = None,
        max_b: Optional[float] = None,
    ) -> None:
        """
        Update a stretch configuration.

        Args:
            image_index: The index of the image.
            stretch_index: The index of the stretch.
            name: Optional new name for the stretch.
            min_r, max_r, min_g, max_g, min_b, max_b: Optional new stretch values.
        """
        # Implementation details...

    # Band operations
    def add_band(self, index: int, band: Optional[Band] = None) -> int:
        """
        Add a band to an image.

        Args:
            index: The index of the image.
            band: Optional band configuration.

        Returns:
            int: The index of the added band.
        """
        # Implementation details...
        return 0

    def remove_band(self, index: int, band_index: int) -> None:
        """
        Remove a band from an image.

        Args:
            index: The index of the image.
            band_index: The index of the band to remove.
        """
        # Implementation details...

    def update_band(
        self,
        index: int,
        band_index: int,
        name: Optional[str] = None,
        r: Optional[int] = None,
        g: Optional[int] = None,
        b: Optional[int] = None,
    ) -> None:
        """
        Update a band configuration.

        Args:
            index: The index of the image.
            band_index: The index of the band.
            name: Optional new name for the band.
            r, g, b: Optional new band values.
        """
        # Implementation details...

    # Plot operations
    def add_plot(self, roi: ROI) -> None:
        """
        Add a plot for an ROI.

        Args:
            roi: The ROI to create a plot from.
        """
        # Implementation details...

    def get_plots(self, index: int) -> List[Plot]:
        """
        Get all plots for an image.

        Args:
            index: The index of the image.

        Returns:
            List[Plot]: A list of plots.
        """
        # Implementation details...
        return []
