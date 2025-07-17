"""
Tool Registry

A registry for managing available viewport tools.
"""

from typing import Dict, List, Type, Set

from varda.features.components.protocols import ViewportTool
from varda.features.components.viewport_tools.pixel_select_tool import PixelSelectTool
from varda.features.components.viewport_tools.roi_tools import (
    FreehandROITool,
    RectangleROITool,
    EllipseROITool,
    PolygonROITool,
)


class ToolRegistry:
    """
    Registry for viewport tools.

    Manages the available tool classes and provides methods for retrieving
    tools by category or other criteria.
    """

    _instance = None

    def __new__(cls):
        """Singleton pattern to ensure only one registry exists."""
        if cls._instance is None:
            cls._instance = super(ToolRegistry, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the registry if not already initialized."""
        if self._initialized:
            return

        self._tools: Set[Type[ViewportTool]] = set()
        self._categories: Dict[str, List[Type[ViewportTool]]] = {}
        self._initialized = True

        # Register built-in tools
        self.registerBuiltinTools()

    def registerTool(self, toolClass: Type[ViewportTool]) -> None:
        """
        Register a tool class with the registry.

        Args:
            toolClass: The tool class to register
        """
        if not issubclass(toolClass, ViewportTool):
            raise TypeError(f"Tool class must be a subclass of Tool, got {toolClass}")

        self._tools.add(toolClass)

        # Add to category dictionary
        category = toolClass.toolCategory
        if category not in self._categories:
            self._categories[category] = []
        self._categories[category].append(toolClass)

    def unregisterTool(self, toolClass: Type[ViewportTool]) -> None:
        """
        Unregister a tool class from the registry.

        Args:
            toolClass: The tool class to unregister
        """
        if toolClass in self._tools:
            self._tools.remove(toolClass)

            # Remove from category dictionary
            category = toolClass.toolCategory
            if category in self._categories and toolClass in self._categories[category]:
                self._categories[category].remove(toolClass)
                if not self._categories[category]:
                    del self._categories[category]

    def getTools(self) -> List[Type[ViewportTool]]:
        """
        Get all registered tool classes.

        Returns:
            List of registered tool classes
        """
        return list(self._tools)

    def getToolsByCategory(self, category: str) -> List[Type[ViewportTool]]:
        """
        Get all registered tool classes in a specific category.

        Args:
            category: The category to filter by

        Returns:
            List of tool classes in the specified category
        """
        return self._categories.get(category, [])

    def getCategories(self) -> List[str]:
        """
        Get all registered tool categories.

        Returns:
            List of category names
        """
        return list(self._categories.keys())

    def registerBuiltinTools(self) -> None:
        """Register the built-in tools."""
        # Selection tools
        self.registerTool(PixelSelectTool)

        # ROI drawing tools
        self.registerTool(FreehandROITool)
        self.registerTool(RectangleROITool)
        self.registerTool(EllipseROITool)
        self.registerTool(PolygonROITool)
