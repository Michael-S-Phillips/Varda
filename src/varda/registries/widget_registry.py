from typing import Dict

from varda.api.types.widget import VWidget


class WidgetRegistry:
    """
    A registry for widgets that can be used in the application.
    """
    _widgets: Dict[str, VWidget] = {}

    def registerWidget(self, name: str, widget_class):
        """
        Register a widget class with a given name.
        """
        if name in self._widgets:
            raise ValueError(f"Widget '{name}' is already registered.")
        self._widgets[name] = widget_class

    def listWidgets(self):
        """
        List all registered widgets.
        """
        return list(self._widgets.keys())

    def __iter__(self):
        """
        Iterate over the registered widgets.
        """
        return iter(self._widgets.items())

    def __getitem__(self, name: str):
        """
        Get a widget by its name.
        """
        return self._widgets.get(name)