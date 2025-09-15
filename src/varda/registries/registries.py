"""
Registry implementations for the Varda application.
"""

import logging
from typing import override

from PyQt6.QtCore import pyqtSignal, QObject
from PyQt6.QtWidgets import QWidget

from varda.image_processing.image_processing_protocol import ImageProcess

logger = logging.getLogger(__name__)


class BaseRegistry(QObject):
    """
    Implementation of the Registry protocol.
    Most of the registries have the same functionality, hence this base class.
    """

    sigItemRegistered = pyqtSignal(str, object)
    sigItemUnregistered = pyqtSignal(str, object)

    def __init__(self):
        super().__init__()
        self.registryItems = {}

    def __contains__(self, key):
        """Check if an item is registered."""
        return key in self.registryItems

    def __len__(self):
        """Get the number of registered items."""
        return len(self.registryItems)

    def __iter__(self):
        """Iterate over the registered items."""
        yield from self.registryItems.items()

    def __getitem__(self, key):
        """Get an item by its name."""
        if key in self:
            return self.registryItems[key]
        else:
            raise KeyError(f"Item '{key}' not found in registry.")

    def __setitem__(self, key, value):
        """Register an item with a given name."""
        if self._itemIsValid(value):
            self.registryItems[key] = value
            self.sigItemRegistered.emit(key, value)
        else:
            raise ValueError(
                f"{value.__name__} is not a valid item for registration in {self.__class__.__name__}!"
            )

    def __delitem__(self, key):
        """Unregister an item by its name."""
        if key in self:
            item = self.registryItems.pop(key)
            self.sigItemUnregistered.emit(key, item)
        else:
            raise KeyError(f"Item '{key}' not found in registry.")

    def register(self, name, item):
        """Register an item."""
        self[name] = item

    def unregister(self, name):
        """Unregister an item."""
        del self[name]

    def _itemIsValid(self, item):
        """
        Check if the item is valid for registration.
        This method should be overridden by subclasses.
        """
        raise NotImplementedError(
            "Registry Subclasses must implement _itemIsValid method."
        )


class WidgetRegistry(BaseRegistry):
    """
    A registry for widgets that can dynamically appear in the application for users.
    """

    def __init__(self):
        super().__init__()

    @override
    def _itemIsValid(self, item):
        """
        Check if the item is a valid widget for registration.
        """
        return issubclass(item, QWidget)


class ImageProcessRegistry(BaseRegistry):
    """
    Registry for image processing functions or classes.
    """

    def __init__(self):
        super().__init__()

    @override
    def _itemIsValid(self, item):
        """
        Check if the item is a valid image processing function or class for registration.
        """
        return isinstance(item, ImageProcess)


class ToolRegistry(BaseRegistry):
    """
    Registry for tools that can be used in the application.
    """

    def __init__(self):
        super().__init__()

    @override
    def _itemIsValid(self, item):
        """
        Check if the item is a valid tool for registration.
        This is a placeholder; implement actual validation logic as needed.
        """
        return hasattr(item, "execute") and callable(getattr(item, "execute"))


class VardaRegistries:
    """Registry to store dynamically loaded widgets and image loaders. (e.g. plugins)"""

    def __init__(self):
        self._widgets = WidgetRegistry()
        # self._imageLoaders = ImageLoaderRegistry()
        self._imageProcesses = ImageProcessRegistry()

    def registerWidget(self, widget):
        """Register a widget class."""
        name = widget.__name__
        self._widgets[name] = widget
        logger.info(f"Registered widget {name}")

    def registerImageLoader(self, loader):
        """Register an image loader class."""
        name = loader.__name__
        self._imageLoaders[name] = loader
        logger.info(f"Registered image loader {name}")

    def registerImageProcess(self, process):
        """Register an image processing function or class."""
        name = process.__name__
        self._imageProcesses[name] = process
        logger.info(f"Registered image process {name}")

    def unregisterWidget(self, widget):
        """Unregister a widget class."""
        name = widget.__name__
        if name in self._widgets:
            del self._widgets[name]
            logger.info(f"Unregistered widget {name}")
        else:
            logger.warning(f"Widget {name} not found in registry.")

    def unregisterImageLoader(self, loader):
        """Unregister an image loader class."""
        name = loader.__name__
        if name in self._imageLoaders:
            del self._imageLoaders[name]
            logger.info(f"Unregistered image loader {name}")
        else:
            logger.warning(f"Image loader {name} not found in registry.")

    def unregisterImageProcess(self, process):
        """Unregister an image processing function or class."""
        name = process.__name__
        if name in self._imageProcesses:
            del self._imageProcesses[name]
            logger.info(f"Unregistered image process {name}")
        else:
            logger.warning(f"Image process {name} not found in registry.")

    @property
    def widgets(self):
        """
        Get the registered widgets.
        """
        return self._widgets

    @property
    def imageLoaders(self):
        """
        Get the registered image loaders.
        """
        return self._imageLoaders

    @property
    def imageProcesses(self):
        """
        Get the registered image processing functions or classes.
        """
        return self._imageProcesses
