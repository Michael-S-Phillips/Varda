"""
Implementation of the _test_project_module_thing service.

This module provides a concrete implementation of the WorkspaceService interface.
"""

import logging
from pathlib import Path
from typing import Optional, List, Any

from PyQt6.QtWidgets import QMessageBox

from varda.common.domain import Image, Metadata, Band, Stretch, Plot, Project, ROI
from varda._test_project_module_thing.api import (
    WorkspaceService,
    WorkspaceChangeType,
    WorkspaceChangeModifier,
)
from varda._test_project_module_thing.infrastructure import ProjectIO, ProjectLoader

logger = logging.getLogger(__name__)


class WorkspaceServiceImpl(WorkspaceService):
    """
    Implementation of the _test_project_module_thing service.

    This class provides methods for managing project data, including
    images, bands, stretches, and ROIs.
    """

    def __init__(self, project_io: ProjectIO):
        """
        Initialize the _test_project_module_thing service.

        Args:
            project_io: The project I/O handler for persistence.
        """
        super().__init__(project_io)
        self._project_data = Project()
        self._is_saved = True
        self._project_loader = ProjectLoader(io=project_io)

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
        # Use the ProjectLoader to save the project
        success, path = self._project_loader.save_project(
            self._project_data, save_as=save_as
        )

        if not success:
            return False

        # Save was successful!
        self._is_saved = True
        self.sigProjectChanged.emit()

        return True

    def load_project(self, load_path: Optional[Path] = None) -> bool:
        """
        Load a project from a file.

        Args:
            load_path: Optional path to the project file.

        Returns:
            bool: True if the load was successful.
        """
        # Ask if user wants to save the current project
        if not self._is_saved:
            msg_box = QMessageBox()
            msg_box.setText("The project has unsaved changes.")
            msg_box.setInformativeText("Do you want to save your changes?")
            msg_box.setStandardButtons(
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel
            )
            ret = msg_box.exec()
            if ret == QMessageBox.StandardButton.Save:
                if not self.save_project():
                    return False
            elif ret == QMessageBox.StandardButton.Cancel:
                logger.info("Project load aborted.")
                return False

        # Use the ProjectLoader to load the project
        success, project = self._project_loader.load_project(load_path=load_path)
        if not success:
            return False

        # Define callback for when all images are loaded
        def on_project_images_loaded():
            # Update the _test_project_module_thing with the loaded Project data
            self._project_data = project

            # Emit signal to notify views of the project change
            self.sigProjectChanged.emit()
            logger.info("Project loaded successfully")

        # Load the raster data for all images in the project
        self._project_loader.load_project_with_images(project, on_project_images_loaded)

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
        if 0 <= index < len(self._project_data.images):
            return self._project_data.images[index]
        return None

    def add_image(self, image: Image) -> int:
        """
        Add an image to the project.

        Args:
            image: The image to add.

        Returns:
            int: The index of the added image.
        """
        index = len(self._project_data.images)
        image.index = index

        # Set a unique name for the image based on its file path
        if image.metadata.filePath:
            base_name = Path(image.metadata.filePath).stem
            image.metadata.name = base_name
        elif image.metadata.name:
            pass  # Keep the existing name
        else:
            image.metadata.name = f"Image {index}"

        self._project_data.images.append(image)
        self._emit_change(index, WorkspaceChangeType.IMAGE, WorkspaceChangeModifier.ADD)
        return index

    def load_new_image(self, path: Optional[Path] = None) -> Optional[int]:
        """
        Load a new image from a file.

        Args:
            path: Optional path to the image file.

        Returns:
            int: The index of the loaded image, or None if loading failed.
        """
        if self._image_loading_service is None:
            logger.error("Image loading service not set")
            return None

        self._image_loading_service.loadImageData(path, self.create_image)
        return None  # The actual index will be returned via the callback

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
        # If stretch is not provided, create default stretches
        if stretch is None:
            stretch = [Stretch.createDefault()]

        # Ensure band configuration exists
        if not band:
            if metadata.defaultBand:
                band = [metadata.defaultBand]
            else:
                band = [Band.createDefault()]

        # Create the image
        image = Image(
            raster=raster,
            metadata=metadata,
            stretch=stretch,
            band=band,
            plots=plot if plot else [],
            index=len(self._project_data.images),
        )

        # Add validation warnings
        if len(image.stretch) == 0:
            logger.warning("Image Stretch list is empty. This may cause errors.")
        if len(image.band) == 0:
            logger.warning("Image Band list is empty. This may cause errors.")

        return self.add_image(image)

    def remove_image(self, index: int) -> None:
        """
        Remove an image from the project.

        Args:
            index: The index of the image to remove.
        """
        # First remove all ROIs associated with this image
        rois_to_remove = []
        for roi in self._project_data.rois:
            if index in roi.image_indices:
                rois_to_remove.append(roi)

        for roi in rois_to_remove:
            self._project_data.rois.remove(roi)

        # Then remove the image
        self._project_data.images.pop(index)
        self._emit_change(
            index, WorkspaceChangeType.IMAGE, WorkspaceChangeModifier.REMOVE
        )

    def get_all_images(self) -> List[Image]:
        """
        Get all images in the project.

        Returns:
            List[Image]: A list of all images.
        """
        return self._project_data.images

    # Metadata operations
    def update_metadata(self, index: int, key: str, value: Any) -> None:
        """
        Update a metadata field for an image.

        Args:
            index: The index of the image.
            key: The metadata key to update.
            value: The new value.
        """
        metadata = self._project_data.images[index].metadata
        if hasattr(metadata, f"_{key}"):
            setattr(metadata, f"_{key}", value)
        else:
            metadata.extraMetadata[key] = value
        self._emit_change(
            index, WorkspaceChangeType.METADATA, WorkspaceChangeModifier.UPDATE
        )

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
        if stretch is None:
            # If no stretch was specified, just add a new default, even if one already exists
            stretch = Stretch.createDefault()
        else:
            # Otherwise, check if the stretch already exists (by comparing all attributes)
            for i, existing_stretch in enumerate(
                self._project_data.images[index].stretch
            ):
                if stretch == existing_stretch:
                    QMessageBox.warning(
                        None,
                        "Duplicate Stretch",
                        "This stretch has already been calculated for this image.",
                    )
                    return i

        self._project_data.images[index].stretch.append(stretch)
        self._emit_change(
            index, WorkspaceChangeType.STRETCH, WorkspaceChangeModifier.ADD
        )
        return len(self._project_data.images[index].stretch) - 1

    def remove_stretch(self, index: int, stretch_index: int) -> None:
        """
        Remove a stretch from an image.

        Args:
            index: The index of the image.
            stretch_index: The index of the stretch to remove.
        """
        self._project_data.images[index].stretch.pop(stretch_index)
        self._emit_change(
            index, WorkspaceChangeType.STRETCH, WorkspaceChangeModifier.REMOVE
        )

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
        try:
            old_stretch = self.get_image(image_index).stretch[stretch_index]

            # Create the updated Stretch using existing values as fallbacks
            new_stretch = Stretch(
                name=name if name is not None else old_stretch.name,
                minR=float(min_r) if min_r is not None else old_stretch.minR,
                maxR=float(max_r) if max_r is not None else old_stretch.maxR,
                minG=float(min_g) if min_g is not None else old_stretch.minG,
                maxG=float(max_g) if max_g is not None else old_stretch.maxG,
                minB=float(min_b) if min_b is not None else old_stretch.minB,
                maxB=float(max_b) if max_b is not None else old_stretch.maxB,
            )

            # Replace the Stretch
            self._project_data.images[image_index].stretch[stretch_index] = new_stretch
            self._emit_change(
                image_index, WorkspaceChangeType.STRETCH, WorkspaceChangeModifier.UPDATE
            )
        except Exception as e:
            logger.error(f"Error updating stretch: {e}")

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
        if band is None:
            band = Band.createDefault()
        self._project_data.images[index].band.append(band)
        self._emit_change(index, WorkspaceChangeType.BAND, WorkspaceChangeModifier.ADD)
        return len(self._project_data.images[index].band) - 1

    def remove_band(self, index: int, band_index: int) -> None:
        """
        Remove a band from an image.

        Args:
            index: The index of the image.
            band_index: The index of the band to remove.
        """
        self._project_data.images[index].band.pop(band_index)
        self._emit_change(
            index, WorkspaceChangeType.BAND, WorkspaceChangeModifier.REMOVE
        )

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
        try:
            image = self.get_image(index)
            old_band = image.band[band_index]
            new_band = Band(
                name=name if name else old_band.name,
                r=int(r) if r is not None else old_band.r,
                g=int(g) if g is not None else old_band.g,
                b=int(b) if b is not None else old_band.b,
            )

            # Replace the band
            self._project_data.images[index].band[band_index] = new_band
            self._emit_change(
                index, WorkspaceChangeType.BAND, WorkspaceChangeModifier.UPDATE
            )
            logger.debug(
                f"Updated Band.\n"
                f"  old: {old_band.r}, {old_band.g}, {old_band.b}\n"
                f"  new: {new_band.r}, {new_band.g}, {new_band.b}"
            )
        except Exception as e:
            logger.error(f"Error updating band: {e}")

    # Plot operations
    def add_plot(self, roi: ROI) -> None:
        """
        Add a plot for an ROI.

        Args:
            roi: The ROI to create a plot from.
        """
        if not roi.image_indices:
            logger.warning("Cannot create plot: ROI has no associated images")
            return

        plot = Plot.create(roi)
        self._project_data.images[roi.image_indices[0]].plots.append(plot)
        self._emit_change(
            roi.image_indices[0], WorkspaceChangeType.PLOT, WorkspaceChangeModifier.ADD
        )

    def get_plots(self, index: int) -> List[Plot]:
        """
        Get all plots for an image.

        Returns:
            List[Plot]: A list of plots.
        """
        if index not in range(len(self._project_data.images)):
            return []
        return self._project_data.images[index].plots

    # ROI operations
    def add_roi(self, roi: ROI) -> str:
        """
        Add an ROI to the project.

        Args:
            roi: The ROI to add.

        Returns:
            str: The ID of the added ROI.
        """
        self._project_data.rois.append(roi)
        for image_index in roi.image_indices:
            self._emit_change(
                image_index, WorkspaceChangeType.ROI, WorkspaceChangeModifier.ADD
            )
        return roi.id

    def remove_roi(self, roi_id: str) -> bool:
        """
        Remove an ROI from the project.

        Args:
            roi_id: The ID of the ROI to remove.

        Returns:
            bool: True if the ROI was removed, False otherwise.
        """
        for i, roi in enumerate(self._project_data.rois):
            if roi.id == roi_id:
                image_indices = roi.image_indices.copy()
                self._project_data.rois.pop(i)
                for image_index in image_indices:
                    self._emit_change(
                        image_index,
                        WorkspaceChangeType.ROI,
                        WorkspaceChangeModifier.REMOVE,
                    )
                return True
        return False

    def update_roi(self, roi_id: str, **kwargs) -> bool:
        """
        Update an ROI.

        Args:
            roi_id: The ID of the ROI to update.
            **kwargs: The attributes to update.

        Returns:
            bool: True if the ROI was updated, False otherwise.
        """
        for roi in self._project_data.rois:
            if roi.id == roi_id:
                for key, value in kwargs.items():
                    if hasattr(roi, key):
                        setattr(roi, key, value)

                for image_index in roi.image_indices:
                    self._emit_change(
                        image_index,
                        WorkspaceChangeType.ROI,
                        WorkspaceChangeModifier.UPDATE,
                    )
                return True
        return False

    def get_roi(self, roi_id: str) -> Optional[ROI]:
        """
        Get an ROI by ID.

        Args:
            roi_id: The ID of the ROI to get.

        Returns:
            ROI: The ROI with the specified ID, or None if not found.
        """
        for roi in self._project_data.rois:
            if roi.id == roi_id:
                return roi
        return None

    def get_rois_for_image(self, image_index: int) -> List[ROI]:
        """
        Get all ROIs associated with an image.

        Args:
            image_index: The index of the image.

        Returns:
            List[ROI]: A list of ROIs associated with the image.
        """
        return [
            roi for roi in self._project_data.rois if image_index in roi.image_indices
        ]

    def get_images_for_roi(self, roi_id: str) -> List[int]:
        """
        Get all image indices associated with an ROI.

        Args:
            roi_id: The ID of the ROI.

        Returns:
            List[int]: A list of image indices associated with the ROI.
        """
        for roi in self._project_data.rois:
            if roi.id == roi_id:
                return roi.image_indices
        return []

    # Helper methods
    def _emit_change(
        self, index: int, change_type: str, change_modifier: Optional[str] = None
    ) -> None:
        """
        Emit a data change signal.

        Args:
            index: The index of the changed item.
            change_type: The type of change.
            change_modifier: Optional modifier for the change.
        """
        self._is_saved = False

        # To support existing code which expects 2 arguments, we simply emit both versions of the signal
        if change_modifier is not None:
            self.sigDataChanged[int, str, str].emit(index, change_type, change_modifier)
        self.sigDataChanged[int, str].emit(index, change_type)
