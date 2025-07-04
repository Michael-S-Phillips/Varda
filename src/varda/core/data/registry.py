import logging
from typing import Protocol, override

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget

from varda.app.services.load_image.loaders import AbstractImageLoader

logger = logging.getLogger(__name__)


class VardaRegistries:
    """Registry to store dynamically loaded widgets and image loaders. (e.g. plugins)"""

    def __init__(self):
        self._widgets = WidgetRegistry()
        self._imageLoaders = ImageLoaderRegistry()

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
        self._imageLoaders.unregisterLoader(loader)

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


class IRegistry(Protocol):
    """
    Protocol for a registry of items that emits signals for updates.
    Implements magic methods for more convenient access.
    """

    sigItemRegistered = pyqtSignal(str, object)
    sigItemUnregistered = pyqtSignal(str, object)

    def __init__(self):
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

    def _itemIsValid(self, item):
        """
        Check if the item is valid for registration.
        This method should be overridden by subclasses.
        """
        raise NotImplementedError(
            "Registry Subclasses must implement _itemIsValid method."
        )


class WidgetRegistry(IRegistry):
    """
    A registry for widgets that can dynamically appear in the application for users.
    """

    @override
    def _itemIsValid(self, item):
        """
        Check if the item is a valid widget for registration.
        """
        return issubclass(item, QWidget)


class ImageLoaderRegistry(IRegistry):
    """
    Registry for image loaders that can be used to load images in the application.
    """

    @override
    def _itemIsValid(self, item):
        """
        Check if the item is a valid image loader for registration.
        """
        return issubclass(item, AbstractImageLoader)
