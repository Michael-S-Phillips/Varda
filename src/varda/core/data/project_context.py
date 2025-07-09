# varda/core/data/project_context.py
# standard library
import json
import logging
import os
from pathlib import Path
from typing import Any, List, Dict
from enum import Enum
import tempfile

# third party imports
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QFileDialog,
    QMessageBox,
)
import numpy as np

# local imports
from varda.core.entities import Image, Metadata, Band, Stretch, ROI, Plot
from varda.app.services.load_image import ImageLoadingService
from varda.core.utilities.signal_utils import guard_signals
from varda.gui.widgets import FileInputDialog

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

    def __init__(self):
        super().__init__()
        self._images: List[Image] = []
        self.currentProj: Path = None
        self.isSaved: bool = True
        self._imageLoadingService = ImageLoadingService()
        self._handling_change = False  # Flag to prevent recursive signal handling

        # Initialize the ROI Manager
        from varda.core.data.roi_manager import ROIManager

        self.roiManager = ROIManager()

        # Flag for generating stretch presets during image creation
        self._generate_stretch_presets = True

    def getProjectName(self):
        """Get the name of the current project, or 'None' if no project is open."""
        if self.currentProj is None:
            return "None"
        return self.currentProj.name

    @guard_signals
    def saveProject(self, saveAs=False):
        """
        Safely writes project data to disk.

        Args:
            saveAs: If True, prompt for a new file path regardless of current project.

        Returns:
            bool: True if the save was successful, False otherwise.
        """
        # If we are not in an existing project, OR if the user wants to save to a new file,
        # prompt for a path and update currentProj
        if self.currentProj is None or saveAs is True:
            fileName = QFileDialog.getSaveFileName(
                None, "Save File", "../", "Varda project file (*.varda)"
            )
            if fileName[0]:
                self.currentProj = Path(fileName[0])
                self.sigProjectChanged.emit()
            else:
                return False

        # Write new data to a temp file, then replace the original file only if the write operation was successful.
        # This avoids losing data if the write operation fails somehow.
        saveData = self.serialize()
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                dir=self.currentProj.parent,
                prefix=self.currentProj.name,
                suffix=".tmp",
                delete=False,
            ) as tempFile:
                json.dump(saveData, tempFile, indent=4, cls=NumpyJSONEncoder)
                tempFile.flush()

            os.replace(tempFile.name, self.currentProj)
            self.isSaved = True
            logger.info(f"Project saved to {self.currentProj}")
            return True
        except Exception as e:
            logger.error(f"Failed to save project! {e}")
            # Cleanup temp file
            if tempFile and Path(tempFile.name).exists():
                os.remove(tempFile.name)
            return False

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

        f: str = None
        if loadPath is None:
            f, _ = QFileDialog.getOpenFileName(
                None, "Open File", "", "Varda project file (*.varda)"
            )
            if not f:
                return False

        loadPath = f if f is not None else loadPath

        try:
            with open(loadPath, "r") as file:
                self.deserialize(file.name, json.load(file))
            logger.info(f"Loaded project from {loadPath}")
            self.sigProjectChanged.emit()
            return True
        except Exception as e:
            logger.error(f"Error loading project: {e}")
            QMessageBox.critical(None, "Error", f"Failed to load project: {e}")
            return False

    def serialize(self):
        """
        Serialize the project data into a JSON-compatible dictionary.

        Returns:
            dict: The serialized project data.
        """
        imageDictList = [
            {
                "metadata": image.metadata.serialize(),
                "stretch": [stretch.serialize() for stretch in image.stretch],
                "band": [band.serialize() for band in image.band],
            }
            for image in self._images
        ]

        # Serialize the ROI Manager
        roi_manager_data = (
            self.roiManager.serialize() if hasattr(self, "roi_manager") else {}
        )

        return {"images": imageDictList, "roi_manager": roi_manager_data}

    def deserialize(self, projectName, data):
        """
        Deserialize project data from a dictionary and update the project state.

        Args:
            projectName: The path to the project file.
            data: The deserialized project data.

        Returns:
            bool: True if successful, False otherwise.
        """
        # Store current state to restore in case of failure
        imagesTemp = self._images
        projectNameTemp = self.currentProj
        roi_manager_temp = self.roiManager if hasattr(self, "roi_manager") else None

        # Temporarily disable stretch preset generation during deserialization
        # since we're loading existing stretches from the file
        original_generate_presets = self._generate_stretch_presets
        self._generate_stretch_presets = False

        try:
            self.currentProj = Path(projectName)
            self._images = []
            imageDictList = data["images"]

            # Track completed loads to emit signals after all images are loaded
            expected_loads = len(imageDictList)
            completed_loads = 0

            def on_image_loaded(raster, metadata, stretch, band):
                """Callback for when an individual image finishes loading during deserialization."""
                nonlocal completed_loads

                # Create the image with the deserialized data
                # Temporarily disable signal guards for this specific operation
                old_handling = self._handling_change
                self._handling_change = False
                try:
                    image_index = self.createImage(
                        raster=raster,
                        metadata=metadata,
                        stretch=stretch,
                        band=band,
                    )
                    completed_loads += 1
                    logger.info(
                        f"Loaded image {completed_loads}/{expected_loads} during deserialization"
                    )

                    # If this is the last image, emit project changed signal
                    if completed_loads == expected_loads:
                        self.sigProjectChanged.emit()
                        logger.info(
                            "All images loaded successfully during deserialization"
                        )

                finally:
                    self._handling_change = old_handling

            for imageDict in imageDictList:
                metadata = Metadata.deserialize(imageDict["metadata"])
                stretch = [
                    Stretch.deserialize(stretch) for stretch in imageDict["stretch"]
                ]
                band = [Band.deserialize(band) for band in imageDict["band"]]

                # Check whether file paths exist. If not, prompt user for updated one.
                oldPath = Path(metadata.filePath)
                if not oldPath.exists():
                    logger.warning(f"Image {oldPath} does not exist!")
                    newPath = Path(
                        FileInputDialog.getFilePath(
                            f"Cannot find {oldPath}. Please locate this image.",
                            fileFilter=f"Image File ({oldPath.name})",
                        )
                    )

                    if newPath.name == oldPath.name:
                        metadata.filePath = str(newPath)
                    else:
                        logger.info(f"Skipping image {oldPath}")
                        expected_loads -= 1  # Reduce expected count for skipped images
                        continue

                # Create callback with captured variables for this iteration
                self._imageLoadingService.loadImageData(
                    metadata.filePath,
                    lambda raster, _, m=metadata, s=stretch, b=band: on_image_loaded(
                        raster, m, s, b
                    ),
                )

            # Deserialize ROI Manager
            if "roi_manager" in data:
                from varda.core.data.roi_manager import ROIManager

                self.roiManager = ROIManager.deserialize(data["roi_manager"], self)
            else:
                # If no ROI Manager in the data, create a new one
                from varda.core.data.roi_manager import ROIManager

                self.roiManager = ROIManager(self)

            # If no images to load, emit the signal immediately
            if expected_loads == 0:
                self.sigProjectChanged.emit()

            return True

        except Exception as e:
            logger.error(f"Project Load Aborted! Error: {e}")
            # Restore previous project state
            self.currentProj = projectNameTemp
            self._images = imagesTemp
            if roi_manager_temp:
                self.roiManager = roi_manager_temp
            return False
        finally:
            # Always restore the original preset generation setting
            self._generate_stretch_presets = original_generate_presets

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
                    from varda.app.services.stretch_utils import StretchPresets

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


class NumpyJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles numpy data types and bytes objects."""

    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, bytes):
            try:
                return obj.decode("utf-8")
            except UnicodeDecodeError:
                return list(obj)
        return super().default(obj)
