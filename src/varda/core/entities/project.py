from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict
import uuid

import numpy as np

from varda.app.project.roi_manager import ROIManager
from varda.common.domain import ROI
from varda.core.entities import Image, Metadata, Stretch, Band


@dataclass
class Project:
    """
    Data representation of a Varda project.
    """

    path: Optional[Path] = None
    images: ImageTable = field(default_factory=ImageTable)
    stretches: StretchTable = field(default_factory=StretchTable)
    bands: BandTable = field(default_factory=BandTable)
    rois: list[ROI] = field(default_factory=list)

    ImageStretchAssociations
    ImageBandAssociaions

    @property
    def name(self) -> str:
        """Get the project name (derived from the filename)."""
        if self.path is None:
            return None
        return self.path.name

    @property
    def directory(self) -> Path | None:
        """Get the directory containing the project file."""
        if self.path is None:
            return None
        return self.path.parent

    def serialize(self):
        return {
            "path": str(self.path) if self.path else None,
            "images": self.images.serialize(),
            "stretches": self.stretches.serialize(),
            "bands": self.bands.serialize(),
        }

    @classmethod
    def deserialize(cls, data: dict) -> "Project":
        """
        Populate the project from a serialized dictionary.

        Args:
            data (dict): The serialized project data.

        Returns:
            Project: The populated project instance.
        """
        path = Path(data["path"]) if data.get("path") else None
        images = []
        for i, imgData in enumerate(data.get("images", [])):
            metadata = Metadata.deserialize(imgData.get("metadata", {}))
            stretches = [Stretch.deserialize(s) for s in imgData.get("stretch", [])]
            bands = [Band.deserialize(b) for b in imgData.get("band", [])]

            # Create the image with raster=None
            # The raster data will be loaded separately by the ProjectLoader
            # This is a clean separation of concerns - the Project entity handles
            # the structure and metadata, while the application layer handles
            # loading the actual image data
            image = Image(
                raster=None,
                metadata=metadata,
                stretch=stretches,
                band=bands,
                index=i,
            )
            images.append(image)

        if "roiManager" in data:
            roiManager = ROIManager.deserialize(data["roiManager"])
        else:
            roiManager = ROIManager()

        return cls(path=path, images=images, roiManager=roiManager)


class ImageTable:
    def __init__(self):
        self._images: Dict[int, Image] = {}

    def addImage(self, image: Image):
        self._images[uuid.uuid4()] = image

    def removeImage(self, id):
        del self._images[id]

    def getImage(self, id):
        return self._images[id]

    def getAllImages(self):
        return self._images

    def serialize(self):
        def serializeImage(image):
            return {"raster": img.raster, "metadata": img.metadata.serialize()}

        return {id: serializeImage(img) for id, img in self._images.items()}

    @classmethod
    def deserialize(cls, data):
        self._images
        for id, img in data.items():
            self._images[id] = Image.deserialize(img)


class StretchTable:
    def __init__(self):
        self._stretches: Dict[int, Stretch] = {}

    def add(self, stretch: Stretch):
        self._stretches[uuid.uuid4()] = stretch

    def remove(self, id):
        del self._stretches[id]

    def get(self, id):
        return self._stretches[id]

    def getAll(self):
        return self._stretches

    def serialize(self):
        def serializeStretch(stretch):
            return (
                stretch.name,
                stretch.minR,
                stretch.maxR,
                stretch.minG,
                stretch.maxG,
                stretch.minB,
                stretch.maxB,
            )

        return {
            id: serializeStretch(stretch) for id, stretch in self._stretches.items()
        }

    def deserialize(self, data):
        def deserializeStretch(stretchData):
            return Stretch(
                name=stretchData[0],
                minR=stretchData[1],
                maxR=stretchData[2],
                minG=stretchData[3],
                maxG=stretchData[4],
                minB=stretchData[5],
                maxB=stretchData[6],
            )

        self._stretches = {
            id: deserializeStretch(stretch) for id, stretch in data.items()
        }


class BandTable:
    def __init__(self):
        self._bands: Dict[int, Band] = {}

    def add(self, band: Band):
        self._bands[uuid.uuid4()] = band

    def remove(self, id):
        del self._bands[id]

    def get(self, id):
        return self._bands[id]

    def getAll(self):
        return self._bands

    def serialize(self):
        def serializeBand(band):
            return (band.name, band.r, band.g, band.b)

        return {id: serializeBand() for id, band in self._bands.items()}

    def deserialize(self, data):
        def deserializeBand(bandData):
            return Band(name=bandData[0], r=bandData[1], g=bandData[2], b=bandData[3])

        self._bands = {id: deserializeBand(band) for id, band in data.items()}


class RoiTable:
    def __init__(self):
        self._rois: Dict[int, ROI] = {}

    def add(self, roi: ROI):
        self._rois[uuid.uuid4()] = roi

    def remove(self, id):
        del self._rois[id]

    def get(self, id):
        return self._rois[id]

    def getAll(self):
        return self._rois


class ImageStretchAssociations:
    def __init__(self, imageTable, stretchTable):
        self._associations: Dict[int, int] = {}
        self._imageTable = imageTable
        self._stretchTable = stretchTable

    def associate(self, imageId: int, stretchId: int):
        self._associations[imageId] = stretchId

    def getStretchesForImage(self, imageId: int) -> List[Stretch]:
        stretchId = self._associations.get(imageId)
        if stretchId is None:
            return []
        return [self._stretchTable.get(stretchId)]
