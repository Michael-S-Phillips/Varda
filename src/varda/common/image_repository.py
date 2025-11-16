from dataclasses import dataclass
import uuid
import logging

import affine
import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal
from rasterio import CRS
from varda.image_loading import ImageLoadingService

import varda
from varda.common.entities import Metadata


logger = logging.getLogger(__name__)


@dataclass
class Image:
    id: str
    filePath: str
    resolution: tuple[int, int]
    rasterData: np.ndarray | None = None
    name: str | None = None
    bandNames: np.ndarray | None = None
    defaultBands: tuple[int, int, int] | None = None
    nodata: float | None = None
    crs: CRS | None = None
    transform: affine.Affine | None = None


class ImageRepository(QObject):

    sigImageAdded: pyqtSignal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.images: dict[str, Image] = {}
        self._imageLoadingService = ImageLoadingService()

    def newImage(self, filePath=None):
        def _onImageLoadSuccess(raster: np.ndarray, metadata: Metadata):
            img = Image(
                id=str(uuid.uuid4()),
                filePath=metadata.filePath,
                resolution=(raster.shape[0], raster.shape[1]),
                rasterData=raster,
                name=metadata.name,
                bandNames=metadata.wavelengths,
                nodata=metadata.dataIgnore,
                crs=metadata.crs,
                transform=metadata.transform,
            )
            self.addImage(img)

        def _onImageLoadFailure():
            varda.log.error(f"Failed to load image from {filePath}!")

        self._imageLoadingService.load_image_data(
            filePath, _onImageLoadSuccess, _onImageLoadFailure
        )

    def addImage(self, img):
        self.images[img.id] = img
        self.sigImageAdded.emit()

    def getImage(self, id):
        return self.images[id]
