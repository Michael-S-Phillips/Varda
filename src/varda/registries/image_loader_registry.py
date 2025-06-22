from typing import Dict

from varda.core.utilities.load_image.loaders import AbstractImageLoader


class ImageLoaderRegistry:
    """
    Registry for image loaders.
    """
    _loaders: Dict[str, AbstractImageLoader] = {}


    def registerLoader(self, name, loader):
        """
        Register an image loader with a given name.
        """
        self._loaders[name] = loader

    def getLoader(self, name):
        """
        Get an image loader by name.
        """
        return self._loaders.get(name)

    def listLoaders(self):
        """
        List all registered image loaders.
        """
        return list(self._loaders.keys())