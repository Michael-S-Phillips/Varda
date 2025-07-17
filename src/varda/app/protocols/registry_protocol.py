"""
Protocol for registries that can register and unregister items.
"""

from typing import Protocol, Type

from PyQt6.QtCore import pyqtSignal


class Registry(Protocol):
    """
    Protocol for a registry of items that emits signals for updates.
    Implements magic methods for more convenient access.
    """

    sigItemRegistered: pyqtSignal  # args: (str, object) aka (name, item)
    sigItemUnregistered: pyqtSignal  # args: (str, object) aka (name, item)

    def register(self, name, item):
        """Register an item."""
        ...

    def unregister(self, name):
        """Unregister an item."""
        ...

    def __iter__(self):
        """Iterate over the registered items."""
        ...

    def __getitem__(self, key):
        """Get an item by its name."""
        ...

    def __contains__(self, key):
        """Check if an item is registered."""
        ...

    def __len__(self):
        """Get the number of registered items."""
        ...

    def __delitem__(self, key):
        """Unregister an item by its name."""
        ...

    def __setitem__(self, key, value):
        """Register an item with a given name."""
        ...
