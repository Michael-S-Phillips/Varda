"""
An idea to have a generic clas for all registries. only problem is it complicates a couple things.
"""

from typing import Protocol

from PyQt6.QtCore import pyqtSignal


class IRegistry(Protocol):
    """
    Protocol for a registry of items that emits signals for updates.
    Implements magic methods for more convenient access.
    """

    sigItemRegistered = pyqtSignal(str, object)
    sigItemUnregistered = pyqtSignal(str, object)

    def __init__(self):
        self.registryItems = {}

    def register(self, name, item):
        """Register a widget class."""
        self.registryItems[name] = item
        self.sigItemRegistered.emit(name, item)

    def unregister(self, name):
        """Register an image loader class."""
        item = self.registryItems.pop(name, None)
        self.sigItemUnregistered.emit(name, item)

    def __iter__(self):
        """Iterate over the registered items."""
        yield from self.registryItems.items()

    def __getitem__(self, key):
        """Get an item by its name."""
        if key in self.registryItems:
            return self.registryItems[key]
        raise KeyError(f"Item '{key}' not found in registry.")

    def __contains__(self, key):
        """Check if an item is registered."""
        return key in self.registryItems

    def __len__(self):
        """Get the number of registered items."""
        return len(self.registryItems)

    def __delitem__(self, key):
        """Unregister an item by its name."""
        self.unregister(key)

    def __setitem__(self, key, value):
        """Register an item with a given name."""
        self.register(key, value)
