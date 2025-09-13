from pathlib import Path
from typing import Dict, List, Tuple
import uuid

from varda.project.roi_manager import ROIManager
from varda.common.domain import ROI
from varda.core.entities import Image, Metadata, Stretch, Band


class ImageTable:
    def __init__(self):
        self._images: Dict[str, Image] = {}

    def addImage(self, image: Image):
        self._images[str(uuid.uuid4())] = image

    def removeImage(self, key):
        del self._images[key]

    def getImage(self, key):
        return self._images[key]

    def getAllImages(self):
        return self._images

    def serialize(self):
        def serializeImage(image):
            return {"raster": image.raster, "metadata": image.metadata.serialize()}

        return {key: serializeImage(img) for key, img in self._images.items()}

    def deserialize(self, data):
        self._images = {}
        for key, img in data.items():
            self._images[key] = Image.deserialize(img)


class StretchTable:
    def __init__(self):
        self._stretches: Dict[str, Stretch] = {}

    def add(self, stretch: Stretch):
        self._stretches[str(uuid.uuid4())] = stretch

    def get(self, key):
        if type(key) is list | tuple:
            return [self._stretches.get(k, None).clone() for k in key]
        return self._stretches.get(key, None).clone()

    def update(
        self,
        key,
        name: str = None,
        minR: float = None,
        maxR: float = None,
        minG: float = None,
        maxG: float = None,
        minB: float = None,
        maxB: float = None,
    ):
        stretch = self._stretches.get(key)

        if name is not None:
            stretch.name = name
        if minR is not None:
            stretch.minR = minR
        if maxR is not None:
            stretch.maxR = maxR
        if minG is not None:
            stretch.minG = minG
        if maxG is not None:
            stretch.maxG = maxG
        if minB is not None:
            stretch.minB = minB
        if maxB is not None:
            stretch.maxB = maxB

    def remove(self, key):
        del self._stretches[key]

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
            key: serializeStretch(stretch) for key, stretch in self._stretches.items()
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
            key: deserializeStretch(stretch) for key, stretch in data.items()
        }


class BandTable:
    def __init__(self):
        self._bands: Dict[str, Band] = {}

    def add(self, band: Band):
        self._bands[str(uuid.uuid4())] = band

    def update(self, key, name: str = None, r=None, g=None, b=None):
        band = self._bands.get(key)
        if name is not None:
            band.name = name
        if r is not None:
            band.r = r
        if g is not None:
            band.g = g
        if b is not None:
            band.b = b

    def get(self, key):
        return self._bands[key]

    def remove(self, key):
        del self._bands[key]

    def getAll(self):
        return self._bands

    def serialize(self):
        def serializeBand(band):
            return band.name, band.r, band.g, band.b

        return {key: serializeBand(band) for key, band in self._bands.items()}

    def deserialize(self, data):
        def deserializeBand(bandData):
            return Band(name=bandData[0], r=bandData[1], g=bandData[2], b=bandData[3])

        self._bands = {key: deserializeBand(band) for key, band in data.items()}


class RoiTable:
    def __init__(self):
        self._rois: Dict[str, ROI] = {}

    def add(self, roi: ROI):
        self._rois[str(uuid.uuid4())] = roi

    def remove(self, key):
        del self._rois[key]

    def get(self, key):
        return self._rois[key]

    def getAll(self):
        return self._rois


class ImageStretchAssociations:
    def __init__(self, imageTable, stretchTable):
        self._associations: Dict[str, List[str]] = {}
        self._imageTable = imageTable
        self._stretchTable = stretchTable

    def associate(self, imageId, stretchId):
        self._associations[imageId].append(stretchId)

    def unassociate(self, imageId, stretchId):
        try:
            self._associations[imageId].remove(stretchId)
        except ValueError:
            pass

    def getStretchesForImage(self, imageId) -> Tuple[Stretch]:
        if imageId not in self._associations:
            return tuple()
        stretchIds = self._associations.get(imageId)
        return self._stretchTable.get(stretchIds)

    def serialize(self):
        return self._associations

    def deserialize(self, data):
        self._associations = data


class ImageBandAssociations:
    def __init__(self, imageTable, bandTable):
        self._associations: Dict[str, List[str]] = {}
        self._imageTable = imageTable
        self._stretchTable = bandTable

    def associate(self, imageId, bandId):
        self._associations[imageId].append(bandId)

    def unassociate(self, imageId, bandId):
        try:
            self._associations[imageId].remove(bandId)
        except ValueError:
            pass

    def getBandsForImage(self, imageId) -> Tuple[Band]:
        if imageId not in self._associations:
            return tuple()
        bandIds = self._associations.get(imageId)
        return self._stretchTable.get(bandIds)

    def serialize(self):
        return self._associations

    def deserialize(self, data):
        self._associations = data


class Project:
    """
    Data representation of a Varda project.
    """

    def __init__(self):
        self.path = None
        self.images = ImageTable()
        self.stretches = StretchTable()
        self.bands = BandTable()
        self.rois = RoiTable()
        self.imageStretch = ImageStretchAssociations(self.images, self.stretches)
        self.imageBand = ImageBandAssociations(self.images, self.bands)

    @property
    def name(self):
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
