# varda/app/project/project_context.py
# standard library
import logging
import os
from typing import Any, List
from enum import Enum

# third party imports
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QMessageBox,
)
import numpy as np
from varda.common.image_repository import ImageRepository

from varda.project.project_io import ProjectIO
from varda.project.project_loader import ProjectLoader

# local imports
from varda.common.entities import Project, Image, Metadata, Band, Stretch, Plot

# TODO: Update these imports when components are moved
from varda.image_loading import ImageLoadingService
from varda.utilities.signal_utils import guard_signals

logger = logging.getLogger(__name__)


class ProjectContext(QObject):
    """
    Central data manager for the Varda application.

    Handles all project data including images, ROIs, bands, stretches, and more.
    Uses signals to notify views of data changes.
    """

    class ChangeType(Enum):
        """Enumerator to represent the types of data that may be changed"""

        IMAGE = "image"
        BAND = "band"
        STRETCH = "stretch"
        METADATA = "metadata"
        PLOT = "plot"

    class ChangeModifier(Enum):
        """Enumerator to represent the ways in which data may be changed"""

        ADD = "add"
        REMOVE = "remove"
        UPDATE = "update"

    # Signal that emits when something writes to the projectContext.
    # Overloaded signal, to add support for a new argument without breaking existing code
    sigDataChanged = pyqtSignal([int, ChangeType], [int, ChangeType, ChangeModifier])
    sigProjectChanged = pyqtSignal()

    def __init__(self, io: ProjectIO):
        super().__init__()
        self._projectData = Project()
        self.imageRepository = ImageRepository()
        self._images: List[Image] = []
        self.isSaved: bool = True
        self._imageLoadingService = ImageLoadingService()
        self._projectLoader = ProjectLoader(self._imageLoadingService, io)
        self._handling_change = False  # Flag to prevent recursive signal handling

        # Initialize the ROI Manager
        # TODO: Update this import when ROIManager is moved
        from varda.project.roi_manager import ROIManager

        self.roiManager = ROIManager()

        # Flag for generating stretch presets during image creation
        self._generate_stretch_presets = True

    def getProjectName(self):
        """Get the name of the current project, or 'None' if no project is open."""
        if self._projectData.name is None:
            return "None"
        else:
            return self._projectData.name

    @guard_signals
    def saveProject(self, saveAs=False):
        """
        Safely writes project data to disk.

        Args:
            saveAs: If True, prompt for a new file path regardless of current project.

        Returns:
            bool: True if the save was successful, False otherwise.
        """
        # Update the Project entity with the current images
        self._projectData.images = self._images

        # Update the ROI Manager in the Project entity
        self._projectData.roiManager = self.roiManager

        # Use the ProjectLoader to save the project
        success, path = self._projectLoader.save_project(
            self._projectData, saveAs=saveAs
        )
        if not success:
            return False

        # save was successful!
        self.isSaved = True
        self.sigProjectChanged.emit()

        return True

    @guard_signals
    def loadProject(self, loadPath=None):
        """
        Load a project from a file. If no path is provided, prompt the user to select a file.

        Args:
            loadPath: Optional path to load the project from.

        Returns:
            bool: True if the project was loaded successfully, False otherwise.
        """
        # Ask if user wants to save the current project
        if self.isSaved is False:
            msgBox = QMessageBox()
            msgBox.setText("The project has unsaved changes.")
            msgBox.setInformativeText("Do you want to save your changes?")
            msgBox.setStandardButtons(
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel
            )
            ret = msgBox.exec()
            if ret == QMessageBox.StandardButton.Save:
                if not self.saveProject():
                    return False
            elif ret == QMessageBox.StandardButton.Cancel:
                logger.info("Project load aborted.")
                return False

        # Use the ProjectLoader to load the project
        success, project = self._projectLoader.load_project(loadPath=loadPath)
        if not success:
            return False

        # Clear current images
        self._images = []

        # Define callback for when all images are loaded
        def on_project_images_loaded():
            # Update the ProjectContext with the loaded Project data
            self._projectData = project

            # Create Image objects in ProjectContext from the loaded Project
            for image in project.images:
                # Temporarily disable signal guards for this specific operation
                old_handling = self._handling_change
                self._handling_change = False
                try:
                    image_index = self.createImage(
                        raster=image.raster,
                        metadata=image.metadata,
                        stretch=image.stretch,
                        band=image.band,
                    )
                finally:
                    self._handling_change = old_handling

            # Update ROI Manager
            if hasattr(project, "roiManager"):
                self.roiManager = project.roiManager
            else:
                # If no ROI Manager in the data, create a new one
                # TODO: Update this import when ROIManager is moved
                from varda.project.roi_manager import ROIManager

                self.roiManager = ROIManager(self)

            # Emit signal to notify views of the project change
            self.sigProjectChanged.emit()
            logger.info("Project loaded successfully")

        # Load the raster data for all images in the project
        self._projectLoader.loadProjectImages(project, on_project_images_loaded)

        return True

    # Image Access
    def getImage(self, index) -> Image:
        """
        Retrieve an image by index.

        Args:
            index: The index of the image to retrieve.

        Returns:
            Image: The requested image.

        Raises:
            IndexError: If the index is out of range.
        """
        return self._images[index]

    @guard_signals
    def addImage(self, image: Image):
        """
        Add a new image to the context.

        Args:
            image: The image to add.

        Returns:
            int: The index of the added image.
        """

        def _setName(image: Image):
            """
            Set a unique name for the image based on its index.
            This is used to ensure that each image has a distinct name.
            """

            file_path = image.metadata.filePath
            if file_path:
                base_name = os.path.basename(file_path)
                return os.path.splitext(base_name)[0]
            elif image.metadata.name:
                return image.metadata.name
            else:
                index = len(self._images)
                return f"Image {index}"

        index = len(self._images)
        image.metadata.name = _setName(image)

        self._images.append(image)
        self._emitChange(index, self.ChangeType.IMAGE, self.ChangeModifier.ADD)
        return index

    def loadNewImage(self, path=None):
        """
        Load an image from the given path.

        Args:
            path: Optional path to the image file. If None, a file dialog will be shown.

        Returns:
            int: The index of the newly loaded image, or None if loading failed.
        """
        self.imageRepository.newImage(path)
        self._imageLoadingService.loadImageData(path, self.createImage)

    def createImage(
        self,
        raster: np.ndarray,
        metadata: Metadata,
        stretch: List[Stretch] = None,
        band: List[Band] = None,
        plot: List[Plot] = None,
        ROIview: QWidget = None,
    ):
        """
        Creates a new image with optional defaults for stretch, adding it to the
        project. Unless we're loading from an existing project, a newly
        loaded image usually won't have stretch and band data associated with it yet.

        Args:
            raster: The image raster data.
            metadata: The image metadata.
            stretch: Optional list of stretch configurations.
            band: Optional list of band configurations.
            roi: Optional list of ROIs.
            plot: Optional list of plots.
            ROIview: Optional ROI view widget.

        Returns:
            int: The index of the created image.
        """
        # If stretch is not provided, create default stretches
        if stretch is None:
            try:
                # Start with just a default stretch to avoid too many updates at once
                stretch = [Stretch.createDefault()]

                # Only add a few basic presets if specifically requested
                # This helps prevent recursion issues during initialization
                if self._generate_stretch_presets:
                    # Import here to avoid circular import
                    # TODO: Update this import when StretchPresets is moved
                    from varda.core.stretch_utils import StretchPresets

                    # Get the default band configuration to use for stretch calculations
                    default_band = band[0] if band else Band.createDefault()

                    # Add a few common presets
                    basic_presets = ["min_max", "percentile_2"]
                    for preset_id in basic_presets:
                        try:
                            preset_stretch = StretchPresets.create_stretch_from_preset(
                                preset_id, raster, default_band
                            )
                            stretch.append(preset_stretch)
                        except Exception as e:
                            logger.warning(
                                f"Failed to create preset stretch {preset_id}: {e}"
                            )
            except Exception as e:
                logger.warning(f"Failed to create preset stretches: {e}")
                # Fallback to single default stretch
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
            rois=[],  # ROIs are now managed separately by ROI Manager
            plots=plot if plot else [],
            ROIview=ROIview if ROIview else None,
            index=len(self._images),
        )

        # Add validation warnings
        if len(image.stretch) == 0:
            logger.warning("Image Stretch list is empty. This may cause errors.")
        if len(image.band) == 0:
            logger.warning("Image Band list is empty. This may cause errors.")

        return self.addImage(image)

    @guard_signals
    def removeImage(self, index):
        """
        Remove an image by index.

        Args:
            index: The index of the image to remove.
        """
        # First remove all ROIs associated with this image
        if hasattr(self, "roi_manager"):
            rois = self.roiManager.getROIsForImage(index)
            for roi in rois:
                self.roiManager.removeROI(roi.id)

        # Then remove the image
        self._images.pop(index)
        self._emitChange(index, self.ChangeType.IMAGE, self.ChangeModifier.REMOVE)

    def getAllImages(self):
        """
        Retrieve a list of all the images in the project.

        Returns:
            List[Image]: List of all images.
        """
        return self._images

    # Metadata
    @guard_signals
    def updateMetadata(self, index, key: str, value: Any):
        """
        Update a metadata field.

        Args:
            index: The image index.
            key: The metadata key to update.
            value: The new value.
        """
        metadata = self._images[index].metadata
        if hasattr(metadata, f"_{key}"):
            setattr(metadata, f"_{key}", value)
        else:
            metadata.extraMetadata[key] = value
        self._emitChange(index, self.ChangeType.METADATA, self.ChangeModifier.UPDATE)

    # Stretch Management
    @guard_signals
    def addStretch(self, index, stretch: Stretch = None):
        """
        Add a stretch to an image. If no stretch is provided, use default.

        Args:
            index: The image index.
            stretch: Optional stretch configuration to add.

        Returns:
            int: The index of the new stretch.
        """
        if stretch is None:
            # if no stretch was specified, just add a new default, even if one already exists
            stretch = Stretch.createDefault()
        else:
            # Otherwise, Check if the stretch already exists (by comparing all attributes), and then add
            for i, existing_stretch in enumerate(self._images[index].stretch):
                if stretch == existing_stretch:
                    QMessageBox.warning(
                        None,
                        "Duplicate Stretch",
                        "This stretch has already been calculated for this image.",
                    )
                    return i

        self._images[index].stretch.append(stretch)
        self._emitChange(index, self.ChangeType.STRETCH, self.ChangeModifier.ADD)
        return len(self._images[index].stretch) - 1

    @guard_signals
    def removeStretch(self, index, stretchIndex):
        """
        Remove a stretch by index from an image.

        Args:
            index: The image index.
            stretchIndex: The index of the stretch to remove.
        """
        self._images[index].stretch.pop(stretchIndex)
        self._emitChange(index, self.ChangeType.STRETCH, self.ChangeModifier.REMOVE)

    @guard_signals
    def updateStretch(
        self,
        imageIndex: int,
        stretchIndex: int,
        name: str = None,
        minR: float = None,
        maxR: float = None,
        minG: float = None,
        maxG: float = None,
        minB: float = None,
        maxB: float = None,
    ):
        """
        Update the stretch parameters for a specific image and stretch index.

        When calling this method, only include the arguments you want to change. The
        rest will maintain their current values.

        Args:
            imageIndex: The index of the image.
            stretchIndex: The index of the stretch.
            name: Optional new name for the stretch.
            minR, maxR, minG, maxG, minB, maxB: Optional new stretch values.
        """
        try:
            oldStretch = self.getImage(imageIndex).stretch[stretchIndex]

            # Create the updated Stretch using existing values as fallbacks
            newStretch = Stretch(
                name=name if name is not None else oldStretch.name,
                minR=float(minR) if minR is not None else oldStretch.minR,
                maxR=float(maxR) if maxR is not None else oldStretch.maxR,
                minG=float(minG) if minG is not None else oldStretch.minG,
                maxG=float(maxG) if maxG is not None else oldStretch.maxG,
                minB=float(minB) if minB is not None else oldStretch.minB,
                maxB=float(maxB) if maxB is not None else oldStretch.maxB,
            )
            # Replace the Stretch
            self._images[imageIndex].stretch[stretchIndex] = newStretch
            self._emitChange(
                imageIndex, self.ChangeType.STRETCH, self.ChangeModifier.UPDATE
            )
        except Exception as e:
            logger.error(f"Error updating stretch: {e}")

    # Band Management
    @guard_signals
    def addBand(self, index, band: Band = None):
        """
        Add a band to an image. If no band is provided, use default.

        Args:
            index: The image index.
            band: Optional band configuration to add.

        Returns:
            int: The index of the new band.
        """
        if band is None:
            band = Band.createDefault()
        self._images[index].band.append(band)
        self._emitChange(index, self.ChangeType.BAND, self.ChangeModifier.ADD)
        return len(self._images[index].band) - 1

    @guard_signals
    def removeBand(self, index, bandIndex):
        """
        Remove a band by index from an image.

        Args:
            index: The image index.
            bandIndex: The index of the band to remove.
        """
        self._images[index].band.pop(bandIndex)
        self._emitChange(index, self.ChangeType.BAND, self.ChangeModifier.REMOVE)

    @guard_signals
    def updateBand(
        self,
        index,
        bandIndex,
        name: str = None,
        r: int = None,
        g: int = None,
        b: int = None,
    ):
        """
        Update the band parameters for a specific image and band index.

        When calling this method, only include the arguments you want to change. The
        rest will maintain their current values.

        Args:
            index: The image index.
            bandIndex: The band index.
            name: Optional new name for the band.
            r, g, b: Optional new band values.
        """
        try:
            image = self.getImage(index)
            oldBand = image.band[bandIndex]
            newBand = Band(
                name=name if name else oldBand.name,
                r=int(r) if r is not None else oldBand.r,
                g=int(g) if g is not None else oldBand.g,
                b=int(b) if b is not None else oldBand.b,
            )
            # Replace the band
            self._images[index].band[bandIndex] = newBand
            self._emitChange(index, self.ChangeType.BAND, self.ChangeModifier.UPDATE)
            logger.debug(
                f"Updated Band.\n"
                f"  old: {oldBand.r}, {oldBand.g}, {oldBand.b}\n"
                f"  new: {newBand.r}, {newBand.g}, {newBand.b}"
            )
        except Exception as e:
            logger.error(f"Error updating band: {e}")

    @guard_signals
    def addPlot(self, roi):
        """
        Save a new plot for the image.

        Args:
            roi: The ROI to create a plot from.
        """
        plot = Plot.create(roi)
        self._images[roi.image_indices[0]].plots.append(plot)
        self._emitChange(
            roi.image_indices[0], self.ChangeType.PLOT, self.ChangeModifier.ADD
        )

    def getPlots(self, index):
        """
        Retrieve all saved plots for an image.

        Args:
            index: The image index.

        Returns:
            List[Plot]: List of plots for the image.
        """
        if index not in range(len(self._images)):
            return []
        return self._images[index].plots

    # Helper methods
    def _emitChange(self, index, changeType, changeModifier=None):
        """
        Emit a data change signal.

        Args:
            index: The index of the changed item.
            changeType: The type of change.
            changeModifier: Optional modifier for the change.
        """
        self.isSaved = False

        # To support existing code which expects 2 arguments, we simply emit both versions of the signal
        if changeModifier is not None:
            self.sigDataChanged[int, self.ChangeType, self.ChangeModifier].emit(
                index, changeType, changeModifier
            )
        self.sigDataChanged[int, self.ChangeType].emit(index, changeType)
