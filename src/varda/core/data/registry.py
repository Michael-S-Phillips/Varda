import logging

from PyQt6.QtWidgets import QWidget

from varda.core.utilities.load_image.loaders import AbstractImageLoader

logger = logging.getLogger(__name__)


class Registry:
    """Registry to store dynamically loaded widgets and image loaders. (e.g. plugins)"""

    def __init__(self):
        self._widgets = WidgetRegistry()
        self._imageLoaders = ImageLoaderRegistry()

    def registerWidget(self, widget):
        """Register a widget class."""
        self._widgets.registerWidget(widget)

    def registerImageLoader(self, loader):
        """Register an image loader class."""
        # TODO: validate that class is a valid image loader.
        self._imageLoaders.registerLoader(loader)

    def unregisterWidget(self, widget):
        """Unregister a widget class."""
        self._widgets.unregisterWidget(widget)

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


class WidgetRegistry:
    """
    A registry for widgets that can be used in the application.
    """

    def __init__(self):
        self._widgets = {}

    def __iter__(self):
        """
        Iterate over the registered widgets.
        """
        return iter(self._widgets.items())

    def registerWidget(self, widget: QWidget):
        """
        Register a widget class with a given name.
        """
        if not issubclass(widget, QWidget):
            raise ValueError(f"{widget.__name__} is not a valid widget!")
        self._widgets[widget.__name__] = widget

        logger.info(f"Registered widget {widget.__name__}")

    def unregisterWidget(self, widget: QWidget):
        """
        Unregister a widget class by its name.
        """
        if widget.__name__ in self._widgets:
            del self._widgets[widget.__name__]
            logger.info(f"Unregistered widget {widget.__name__}")
        else:
            logger.warning(f"Widget {widget.__name__} not found in registry.")


class ImageLoaderRegistry:
    """
    Registry for image loaders.
    """

    def __init__(self):
        self._loaders = {}

    def __iter__(self):
        """
        Iterate over the registered widgets.
        """
        return iter(self._loaders.items())

    def registerLoader(self, loader):
        """
        Register an image loader with a given name.
        """
        if not issubclass(loader, AbstractImageLoader):
            raise ValueError(f"{loader.__name__} is not a valid image loader!")
        self._loaders[loader.__name__] = loader
        logger.info(f"Registered image loader {loader.__name__}")

    def unregisterLoader(self, loader):
        """
        Unregister an image loader by its name.
        """
        if loader.__name__ in self._loaders:
            del self._loaders[loader.__name__]
            logger.info(f"Unregistered image loader {loader.__name__}")
        else:
            logger.warning(f"Image loader {loader.__name__} not found in registry.")
