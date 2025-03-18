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
from core.entities import Image, Metadata, Band, Stretch, FreeHandROI, Plot
from core.utilities.load_image import ImageLoadingService
from gui.widgets import FilePathBox

logger = logging.getLogger(__name__)


class ProjectContext(QObject):
    """TODO:"""

    class ChangeType(Enum):
        """Simple enumerator to representing the types of data that can be changed"""

        IMAGE = "image"
        BAND = "band"
        STRETCH = "stretch"
        METADATA = "metadata"
        ROI = "roi"
        PLOT = "plot"
        ROIView = "ROIView"

    # signal that emits when something writes to the projectContext.
    # int argument is the index of the item that was changed.
    sigDataChanged: pyqtSignal = pyqtSignal(int, ChangeType)
    sigProjectChanged: pyqtSignal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._images: List[Image] = []
        self.currentProj: Path = None
        self.isSaved: bool = True
        self._controlPanels = {}
        self._imageLoadingService = ImageLoadingService()

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
        return {"images": imageDictList}

    def deserialize(self, projectName, data):
        imagesTemp = self._images
        projectNameTemp = self.currentProj
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
        except Exception as e:
            logger.error(f"Project Load Aborted! Error: {e}")
            # restore previous project state
            self.currentProj = projectNameTemp
            self._images = imagesTemp

    # Image Access
    def getImage(self, index):
        """Retrieve an image by index."""
        return self._images[index]

    def addImage(self, image: Image):
        """Add a new image to the context."""
        index = len(self._images)
        image.metadata.name = (
            f"Image {index}"  # Assign a unique name based on the index
        )
        self._images.append(image)
        self._emitChange(index, self.ChangeType.IMAGE)
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
        roi: List[FreeHandROI] = None,
        plot: List[Plot] = None,
        ROIview: QWidget = None,
    ):
        """Creates a new image with optional defaults for stretch, adding it to the
        project. Unless we're loading from an existing project, a newly
        loaded image usually won't have stretch and band data associated with it yet
        """
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
        self._emitChange(index, self.ChangeType.IMAGE)

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
        self._emitChange(index, self.ChangeType.METADATA)

    # Stretch Management
    def addStretch(self, index, stretch: Stretch):
        """Add a stretch to an image. Returns the index of the new stretch"""
        self._images[index].stretch.append(stretch)
        self._emitChange(index, self.ChangeType.STRETCH)
        return len(self._images[index].stretch) - 1

    def removeStretch(self, index, stretchIndex):
        """Remove a stretch by index from an image."""
        self._images[index].stretch.pop(stretchIndex)
        self._emitChange(index, self.ChangeType.STRETCH)

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
        self._emitChange(imageIndex, self.ChangeType.STRETCH)

    def replaceStretch(self, index, stretchIndex, newStretch: Stretch):
        """Update a specific stretch."""
        self._images[index].stretch[stretchIndex] = newStretch
        self._emitChange(index, self.ChangeType.STRETCH)

    # Band Management
    def addBand(self, index, band: Any):
        """Add a band to an image. Returns the index of the new band"""
        self._images[index].band.append(band)
        self._emitChange(index, self.ChangeType.BAND)
        return len(self._images[index].band) - 1

    def removeBand(self, index, bandIndex):
        """Remove a band by index from an image."""
        self._images[index].band.pop(bandIndex)
        self._emitChange(index, self.ChangeType.BAND)

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
        self._emitChange(index, self.ChangeType.BAND)
        logger.debug(
            f"Updated Band.\n"
            f"  old: {oldBand.r}, {oldBand.g}, {oldBand.b}\n"
            f"  new: {newBand.r}, {newBand.g}, {newBand.b}"
        )

    # ROI actions
    def addROI(self, index, roi: Any):
        # need to put logic for roi band somewhere
        # call addROI and removeROI in the control panel
        self._images[index].rois.append(roi)
        self._emitChange(index, self.ChangeType.ROI)
        return len(self._images[index].rois) - 1

    def removeROI(self, index, roiIndex):
        self._images[index].rois.pop(roiIndex)
        self._emitChange(index, self.ChangeType.ROI)

    def getROIs(self, index):
        return self._images[index].rois

    # TODO: add data param
    def addPlot(self, roi):
        """
        Save a new plot for the image at the given index.
        """
        plot = Plot.create(roi)
        self._images[roi.imageIndex].plots.append(plot)
        self.sigDataChanged.emit(roi.imageIndex, self.ChangeType.PLOT)

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
    def _emitChange(self, index, changeType):
        self.isSaved = False
        self.sigDataChanged.emit(index, changeType)


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
