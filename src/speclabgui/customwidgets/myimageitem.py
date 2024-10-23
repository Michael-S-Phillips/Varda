from typing import override, Iterable
import pyqtgraph as pg
import numpy as np


class MyImageItem(pg.ImageItem):
    def __init__(self, image: np.ndarray | None=None, **kargs):
        super(MyImageItem, self).__init__(image, **kargs)
        self.fullDataset = None
        self.bands = {'r': 0, 'g': 0, 'b': 0}

    def setDataset(self, data):
        self.fullDataset = data

    def updateBands(self, bands: dict):
        if isinstance(bands, dict):
            self.bands = bands
        elif hasattr(bands, '__iter__') and len(bands) == 3:
            self.bands = {'r': bands[0], 'g': bands[1], 'b': bands[2]}
        else:
            raise ValueError('invalid bands type')

        if self.fullDataset is not None:
            self.image = self.fullDataset[:, :, list(self.bands.values())]
        self.updateImage()


    def updateImageBands(self, bands: dict):

    @override
    def setImage(
            self,
            image: np.ndarray | None = None,
            autoLevels: bool | None = None,
            levelSamples: int = 65536,
            **kwargs
    ):

        super(myImageItem, self).setImage(image, autoLevels, **kwargs)

