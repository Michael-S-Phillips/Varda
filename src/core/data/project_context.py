# standard library
import json
import logging
import os
from pathlib import Path
from typing import Any, List
from enum import Enum
import tempfile

# third party imports
from PyQt6.QtCore import QObject, pyqtSignal, QFileSelector
from PyQt6.QtWidgets import (
    QWidget,
    QFileDialog,
    QDialog,
    QLabel,
    QPushButton,
    QHBoxLayout,
    QVBoxLayout,
    QMessageBox,
)
import numpy as np

# local imports
from core.entities import Image, Metadata, Band, Stretch, freehandROI, Plot
from core.entities.freehandROI import FreehandROI
from core.utilities.load_image import ImageLoadingService
from gui.widgets import FilePathBox

logger = logging.getLogger(__name__)


class ProjectContext(QObject):
    """TODO:"""

    class ChangeType(Enum):
        """Enumerator to represent the types of data that may be changed"""

        IMAGE = "image"
        BAND = "band"
        STRETCH = "stretch"
        METADATA = "metadata"
        ROI = "roi"
        PLOT = "plot"
        ROIView = "ROIView"

    class ChangeModifier(Enum):
        """Enumerator to represent the ways in which data may be changed"""

        ADD = "add"
        REMOVE = "remove"
        UPDATE = "update"

    # signal that emits when something writes to the projectContext.
    # int argument is the index of the item that was changed.

    # overloaded signal, to add support for a new argument without breaking existing code
    sigDataChanged: pyqtSignal = pyqtSignal(
        [int, ChangeType], [int, ChangeType, ChangeModifier]
    )
    sigProjectChanged: pyqtSignal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._images: List[Image] = []
        self.currentProj: Path = None
        self.isSaved: bool = True
        self._controlPanels = {}
        self._imageLoadingService = ImageLoadingService()
        
        # Initialize the ROI Manager
        from core.data.roi_manager import ROIManager
        self.roi_manager = ROIManager(self)

    def getProjectName(self):
        if self.currentProj is None:
            return "None"
        return self.currentProj.name

    def saveProject(self, saveAs=False):
        """Safely writes project data to disk"""

        # if we are not in an existing project, OR if the user wants to save to a new file,
        #  prompt for a path and update currentProj
        if self.currentProj is None or saveAs is True:
            fileName = QFileDialog.getSaveFileName(
                None, "Save File", "../", "Varda project file (*.varda)"
            )
            if fileName[0]:
                self.currentProj = Path(fileName[0])
                self.sigProjectChanged.emit()
            else:
                return

        # write new data to a temp file, then replace the original file only if the write operation was successful.
        # this avoids losing data if the write operation fails somehow.
        saveData = self.serialize()
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                dir=self.currentProj.parent,
                prefix=self.currentProj.name,
                suffix=".tmp",
                delete=False,
            ) as tempFile:
                json.dump(saveData, tempFile, indent=4)
                tempFile.flush()

            os.replace(tempFile.name, self.currentProj)
            self.isSaved = True
            logger.info(f"Project saved to {self.currentProj}")
        except Exception as e:
            logger.error(f"Failed to save project! {e}")
            # cleanup temp file
            if Path(tempFile.name).exists():
                os.remove(tempFile.name)

    def loadProject(self, loadPath=None):
        """Load a project from a file. If no path is provided, prompt the user to select a file."""

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
                self.saveProject()
            elif ret == QMessageBox.StandardButton.Cancel:
                logger.info("Project load aborted.")
                return
            elif ret == QMessageBox.StandardButton.Discard:
                # just let the function execution continue
                pass

        f: str = None
        if loadPath is None:
            f, _ = QFileDialog.getOpenFileName(
                None, "Open File", "", "Varda project file (*.varda)"
            )
        loadPath = f if f is not None else loadPath

        with open(loadPath, "r") as file:
            self.deserialize(file.name, json.load(file))
        logger.info(f"Loaded project from {loadPath}")
        self.sigProjectChanged.emit()

    def serialize(self):
        imageDictList = [
            {
                "metadata": image.metadata.serialize(),
                "stretch": [stretch.serialize() for stretch in image.stretch],
                "band": [band.serialize() for band in image.band],
            }
            for image in self._images
        ]
        
        # Serialize the ROI Manager
        roi_manager_data = self.roi_manager.serialize() if hasattr(self, 'roi_manager') else {}
        
        return {
            "images": imageDictList,
            "roi_manager": roi_manager_data
        }

    def deserialize(self, projectName, data):
        imagesTemp = self._images
        projectNameTemp = self.currentProj
        roi_manager_temp = self.roi_manager if hasattr(self, 'roi_manager') else None
        
        try:
            self.currentProj = Path(projectName)
            self._images = []
            imageDictList = data["images"]
            for imageDict in imageDictList:
                metadata = Metadata.deserialize(imageDict["metadata"])
                stretch = [
                    Stretch.deserialize(stretch) for stretch in imageDict["stretch"]
                ]
                band = [Band.deserialize(band) for band in imageDict["band"]]

                # check whether file paths exist. if not, prompt user for updated one.
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
                        continue

                # this lambda is basically a custom version of loadNewImage, that passes in the data from the json.
                # it's important that we "capture" the variables from the current loop iteration, via default vals
                # because the lambda won't execute until later
                self._imageLoadingService.loadImageData(
                    metadata.filePath,
                    lambda raster, _, m=metadata, s=stretch, b=band: self.createImage(
                        raster=raster,
                        metadata=m,
                        stretch=s,
                        band=b,
                    ),
                )
            
            # Deserialize ROI Manager
            if "roi_manager" in data:
                from core.data.roi_manager import ROIManager
                self.roi_manager = ROIManager.deserialize(data["roi_manager"], self)
            else:
                # If no ROI Manager in the data, create a new one
                from core.data.roi_manager import ROIManager
                self.roi_manager = ROIManager(self)
                
        except Exception as e:
            logger.error(f"Project Load Aborted! Error: {e}")
            # restore previous project state
            self.currentProj = projectNameTemp
            self._images = imagesTemp
            if roi_manager_temp:
                self.roi_manager = roi_manager_temp
    # Image Access
    def getImage(self, index) -> Image:
        """Retrieve an image by index."""
        return self._images[index]

    def addImage(self, image: Image):
        """Add a new image to the context."""
        index = len(self._images)
        image.metadata.name = (
            f"Image {index}"  # Assign a unique name based on the index
        )
        self._images.append(image)
        self._emitChange(index, self.ChangeType.IMAGE, self.ChangeModifier.ADD)
        return index

    def loadNewImage(self, path=None):
        """Load an image from the given path."""
        self._imageLoadingService.loadImageData(path, self.createImage)

    def createImage(
        self,
        raster: np.ndarray,
        metadata: Metadata,
        stretch: List[Stretch] = None,
        band: List[Band] = None,
        roi: List[FreehandROI] = None,
        plot: List[Plot] = None,
        ROIview: QWidget = None,
    ):
        """Creates a new image with optional defaults for stretch, adding it to the
        project. Unless we're loading from an existing project, a newly
        loaded image usually won't have stretch and band data associated with it yet
        """
        # If stretch is not provided, create default stretches
        if stretch is None:
            try:
                # Start with just a default stretch to avoid too many updates at once
                stretch = [Stretch.createDefault()]
                
                # Only add a few basic presets if specifically requested
                # This helps prevent recursion issues during initialization
                if hasattr(self, '_generate_stretch_presets') and self._generate_stretch_presets:
                    # Import here to avoid circular import
                    from core.stretch.stretch_manager import StretchPresets
                    
                    # Add a few common presets
                    basic_presets = ["min_max", "percentile_2"] 
                    for preset_id in basic_presets:
                        try:
                            preset_stretch = StretchPresets.create_stretch_from_preset(preset_id, raster)
                            stretch.append(preset_stretch)
                        except Exception as e:
                            logger.warning(f"Failed to create preset stretch {preset_id}: {e}")
            except Exception as e:
                logger.warning(f"Failed to create preset stretches: {e}")
                # Fallback to single default stretch
                stretch = [Stretch.createDefault()]
        
        # Continue with the rest of the method as before
        image = Image(
            raster,
            metadata,
            stretch if stretch else [Stretch.createDefault()],
            band if band else [Band.createDefault()],
            roi if roi else [],
            plot if plot else [],
            ROIview if ROIview else None,
            len(self._images),
        )
        if len(image.stretch) == 0:
            logger.warning("Image Stretch list is empty. this may cause errors.")
        if len(image.band) == 0:
            logger.warning("Image Band list is empty. this may cause errors.")
        return self.addImage(image)

    def removeImage(self, index):
        """Remove an image by index."""
        self._images.pop(index)
        self._emitChange(index, self.ChangeType.IMAGE, self.ChangeModifier.REMOVE)

    def getAllImages(self):
        """Retrieve a list of all the images in the project"""
        return self._images

    def getControlPanel(self, index, main_window):
        """
        Get or create a control panel for the given image index.

        If a control panel already exists for this image, return it.
        Otherwise, create a new one and store it.
        """
        from core.ui.controlpanel import ControlPanel

        if index not in self._controlPanels:
            self._controlPanels[index] = ControlPanel(main_window)
        return self._controlPanels[index]

    # Metadata
    def updateMetadata(self, index, key: str, value: Any):
        """Update a metadata field."""
        metadata = self._images[index].metadata
        if hasattr(metadata, f"_{key}"):
            setattr(metadata, f"_{key}", value)
        else:
            metadata.extraMetadata[key] = value
        self._emitChange(index, self.ChangeType.METADATA, self.ChangeModifier.UPDATE)

    # Stretch Management
    def addStretch(self, index, stretch: Stretch = None):
        """Add a stretch to an image. If no stretch is provided, use default. Returns index of the new stretch"""
        if stretch is None:
            stretch = Stretch.createDefault()
        self._images[index].stretch.append(stretch)
        self._emitChange(index, self.ChangeType.STRETCH, self.ChangeModifier.ADD)
        return len(self._images[index].stretch) - 1

    def removeStretch(self, index, stretchIndex):
        """Remove a stretch by index from an image."""
        self._images[index].stretch.pop(stretchIndex)
        self._emitChange(index, self.ChangeType.STRETCH, self.ChangeModifier.REMOVE)

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
        """Update the stretch parameters for a specific image and stretch index.

        When calling this method, only include the arguments you want to change. The
        rest will maintain their current values
        """
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
        # replace the Stretch
        self._images[imageIndex].stretch[stretchIndex] = newStretch
        self._emitChange(
            imageIndex, self.ChangeType.STRETCH, self.ChangeModifier.UPDATE
        )

    # Band Management
    def addBand(self, index, band: Band = None):
        """Add a band to an image. If no band is provided, use default. Returns index of the new band"""
        if band is None:
            band = Band.createDefault()
        self._images[index].band.append(band)
        self._emitChange(index, self.ChangeType.BAND, self.ChangeModifier.ADD)
        return len(self._images[index].band) - 1

    def removeBand(self, index, bandIndex):
        """Remove a band by index from an image."""
        self._images[index].band.pop(bandIndex)
        self._emitChange(index, self.ChangeType.BAND, self.ChangeModifier.REMOVE)

    def updateBand(
        self,
        index,
        bandIndex,
        name: str = None,
        r: int = None,
        g: int = None,
        b: int = None,
    ):
        """Update the band parameters for a specific image and band index.

        When calling this method, only include the arguments you want to change. The
        rest will maintain their current values
        """
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

    # --------------------------------------------------------
    # ROI methods that delegate to ROI Manager
    # --------------------------------------------------------
    # Legacy ROI methods - these are updated to use the new ROI Manager
    def addROI(self, index, roi: Any):
        """
        Legacy method to add an ROI to an image.
        Now uses the ROI Manager.
        """
        # Handle both new-style FreehandROI and legacy ROIs
        if isinstance(roi, FreehandROI):
            # New-style ROI
            return self.add_roi(roi, [index])
        else:
            # Legacy ROI format - convert to new format
            try:
                points = np.array(roi.points) if hasattr(roi, 'points') else np.array([])
                color = roi.color if hasattr(roi, 'color') else (255, 0, 0, 128)
                
                # Create a new ROI with data from the legacy one
                new_roi = FreehandROI(
                    points=points,
                    image_indices=[index],
                    color=color,
                    array_slice=getattr(roi, 'arraySlice', None),
                    mean_spectrum=getattr(roi, 'meanSpectrum', None)
                )
                
                return self.add_roi(new_roi, [index])
            except Exception as e:
                logger.error(f"Failed to convert legacy ROI: {e}")
                # Fall back to old behavior
                self._images[index].rois.append(roi)
                self._emitChange(index, self.ChangeType.ROI, self.ChangeModifier.ADD)
                return len(self._images[index].rois) - 1

    def removeROI(self, index, roiIndex):
        """
        Legacy method to remove an ROI from an image.
        Now uses the ROI Manager.
        """
        try:
            # Try to handle as a new-style ROI first
            rois = self.get_rois_for_image(index)
            if roiIndex < len(rois):
                roi_id = rois[roiIndex].id
                return self.remove_roi(roi_id)
            else:
                # Fall back to old behavior
                self._images[index].rois.pop(roiIndex)
                self._emitChange(index, self.ChangeType.ROI, self.ChangeModifier.REMOVE)
                return True
        except Exception as e:
            logger.error(f"Error in removeROI: {e}")
            return False

    def getROIs(self, index):
        """
        Legacy method to get ROIs for an image.
        Now uses the ROI Manager.
        """
        try:
            # Try to get new-style ROIs first
            rois = self.get_rois_for_image(index)
            if rois:
                return rois
            else:
                # Fall back to old behavior
                return self._images[index].rois if index in range(len(self._images)) else []
        except Exception as e:
            logger.error(f"Error in getROIs: {e}")
            return []
        
    def add_roi(self, roi, image_indices=None):
        """Add an ROI to the project"""
        roi_id = self.roi_manager.add_roi(roi, image_indices)
        if roi_id:
            self._emitChange(image_indices[0] if image_indices else 0, self.ChangeType.ROI, self.ChangeModifier.ADD)
        return roi_id

    def remove_roi(self, roi_id):
        """Remove an ROI from the project"""
        roi = self.roi_manager.get_roi(roi_id)
        image_indices = roi.image_indices if roi else []
        result = self.roi_manager.remove_roi(roi_id)
        if result and image_indices:
            self._emitChange(image_indices[0], self.ChangeType.ROI, self.ChangeModifier.REMOVE)
        return result

    def update_roi(self, roi_id, **properties):
        """Update an ROI's properties"""
        roi = self.roi_manager.get_roi(roi_id)
        image_indices = roi.image_indices if roi else []
        result = self.roi_manager.update_roi(roi_id, **properties)
        if result and image_indices:
            self._emitChange(image_indices[0], self.ChangeType.ROI, self.ChangeModifier.UPDATE)
        return result

    def get_roi(self, roi_id):
        """Get an ROI by ID"""
        return self.roi_manager.get_roi(roi_id)

    def get_all_rois(self):
        """Get all ROIs in the project"""
        return self.roi_manager.get_all_rois()

    def get_rois_for_image(self, image_index):
        """Get all ROIs associated with an image"""
        return self.roi_manager.get_rois_for_image(image_index)

    def associate_roi_with_image(self, roi_id, image_index):
        """Associate an ROI with an image"""
        result = self.roi_manager.associate_roi_with_image(roi_id, image_index)
        if result:
            self._emitChange(image_index, self.ChangeType.ROI, self.ChangeModifier.UPDATE)
        return result

    def dissociate_roi_from_image(self, roi_id, image_index):
        """Dissociate an ROI from an image"""
        result = self.roi_manager.dissociate_roi_from_image(roi_id, image_index)
        if result:
            self._emitChange(image_index, self.ChangeType.ROI, self.ChangeModifier.UPDATE)
        return result

    # ROI Table Column methods
    def add_roi_column(self, name, data_type, formula=None):
        """Add a new column to the ROI table"""
        column = self.roi_manager.add_column(name, data_type, formula)
        if column:
            # Signal that ROI table structure has changed
            self._emitChange(0, self.ChangeType.ROI, self.ChangeModifier.UPDATE)
        return column

    def remove_roi_column(self, name):
        """Remove a column from the ROI table"""
        result = self.roi_manager.remove_column(name)
        if result:
            # Signal that ROI table structure has changed
            self._emitChange(0, self.ChangeType.ROI, self.ChangeModifier.UPDATE)
        return result

    def update_roi_column(self, name, **properties):
        """Update a column's properties"""
        result = self.roi_manager.update_column(name, **properties)
        if result:
            # Signal that ROI table structure has changed
            self._emitChange(0, self.ChangeType.ROI, self.ChangeModifier.UPDATE)
        return result

    def get_roi_column(self, name):
        """Get a column by name"""
        return self.roi_manager.get_column(name)

    def get_all_roi_columns(self):
        """Get all columns in the ROI table"""
        return self.roi_manager.get_all_columns()

    def calculate_roi_formulas(self):
        """Calculate all formula columns"""
        self.roi_manager.calculate_formula_columns()
        # Signal that ROI data has changed
        self._emitChange(0, self.ChangeType.ROI, self.ChangeModifier.UPDATE)

    def set_roi_custom_value(self, roi_id, column_name, value):
        """Set a custom value for an ROI"""
        roi = self.roi_manager.get_roi(roi_id)
        if roi:
            roi.set_custom_value(column_name, value)
            image_indices = roi.image_indices
            if image_indices:
                self._emitChange(image_indices[0], self.ChangeType.ROI, self.ChangeModifier.UPDATE)
            return True
        return False

    def get_roi_custom_value(self, roi_id, column_name, default=None):
        """Get a custom value for an ROI"""
        roi = self.roi_manager.get_roi(roi_id)
        if roi:
            return roi.get_custom_value(column_name, default)
        return default
    
    # -------------------------------------------------------
    # metadata editor
    # -------------------------------------------------------
    def openMetadataEditor(self, index):
        """Opens the metadata editor for the specified image."""
        from gui.widgets.metadata_editor import MetadataEditor
        
        if index < 0 or index >= len(self._images):
            logger.warning(f"Invalid image index for metadata editor: {index}")
            return
            
        editor = MetadataEditor(
            self._images[index].metadata,
            self,
            index
        )
        
        # Show the dialog
        if editor.exec():
            # Dialog was accepted - metadata has been updated via direct calls
            # to updateMetadata() by the dialog itself
            logger.info(f"Metadata updated for image {index}")
            
            # Make sure the GUI knows the data changed
            self._emitChange(index, self.ChangeType.METADATA, self.ChangeModifier.UPDATE)
            return True
        
        return False

    # TODO: add data param
    def addPlot(self, roi):
        """
        Save a new plot for the image at the given index.
        """
        plot = Plot.create(roi)
        self._images[roi.image_indices[0]].plots.append(plot)
        self.sigDataChanged.emit(roi.image_indices[0], self.ChangeType.PLOT)

    def getPlots(self, index):
        """Retrieve all saved plots for an image."""
        if index not in range(len(self._images)):
            return []
        return self._images[index].plots

    def setROIView(self, index, view: QObject):
        """
        Retrieve or create the ROI Table for a given image.
        Ensures each image has only one ROI Table open at a time.
        """
        if self._images[index].ROIview is None:
            self._images[index].ROIview = view

        return self._images[index].ROIview

    # Helper methods
    def _emitChange(self, index, changeType, changeModifier):
        self.isSaved = False

        # to support existing code which expects 2 arguments, we simply emit both versions of the signal
        self.sigDataChanged[int, self.ChangeType, self.ChangeModifier].emit(
            index, changeType, changeModifier
        )
        self.sigDataChanged[int, self.ChangeType].emit(index, changeType)


class FileInputDialog(QDialog):
    def __init__(
        self, message="Select a file:", defaultPath="", fileFilter=None, parent=None
    ):
        super().__init__(parent)
        self.setWindowTitle("File Selection")

        # Message label
        self.label = QLabel(message)

        self.fileInput = FilePathBox(defaultPath, fileFilter, parent=self)

        # OK and Cancel buttons
        self.ok_button = QPushButton("OK")
        self.ok_button.clicked.connect(self.accept)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)

        # Layouts
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)

        main_layout = QVBoxLayout()
        main_layout.addWidget(self.label)
        main_layout.addWidget(self.fileInput)
        main_layout.addLayout(button_layout)

        self.setLayout(main_layout)

    @staticmethod
    def getFilePath(
        message="Select a file:", default_path="", fileFilter=None, parent=None
    ):
        """
        Static method to show the dialog and return the selected file path.
        """
        dialog = FileInputDialog(message, default_path, fileFilter, parent)
        if dialog.exec():
            return dialog.fileInput.result  # Return the selected path
        return None  # Return None if cancelled
