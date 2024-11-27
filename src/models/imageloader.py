# standard library

# third party imports
from pathlib import Path

# local imports
from models.abstractimagemodel import AbstractImageModel


class AbstractImageLoader:
    """
    Class to load images from a file path. To be inherited by specific image types.
    """

    def __init__(self, filePath=None):
        self.filePath = filePath
        if self.filePath is None:
            return
        self.load()

    def load(self, filePath=None):
        if filePath:
            self.filePath = filePath
        if self.filePath is None:
            return
        self._loadImage()
        self._loadMetadata()

    def _loadImage(self, filePath=None):
        if filePath:
            self.filePath = filePath
        if self.filePath is None:
            return
        pass

    def _loadMetadata(self, filePath=None):
        if filePath:
            self.filePath = filePath
        if self.filePath is None:
            return
        pass