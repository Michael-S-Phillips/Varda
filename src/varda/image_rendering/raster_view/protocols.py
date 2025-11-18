from typing import Protocol

import pyqtgraph as pg
from PyQt6.QtCore import pyqtSignal
from varda.common.entities import Image
from varda.image_rendering.raster_view import VardaImageItem


class Viewport(Protocol):
    """
    Protocol for a viewport, which is a widget that displays image data.
    The purpose of this is to generalize an interface that can be used by controllers/viewport_tools/workspaces.
    """

    sigImageChanged: pyqtSignal

    def enableSelfUpdating(self):
        """Enable self-updating of the image item."""

    def disableSelfUpdating(self):
        """Disable self-updating of the image item."""

    def refresh(self):
        """Refresh the image display with current settings."""

    def addItem(self, item):
        """Add a graphics item to the viewport"""

    def removeItem(self, item):
        """Remove a graphics item from the viewport"""

    def installTool(self, tool):
        """Install a tool on the viewport."""

    def removeTool(self, tool):
        """Remove a tool from the viewport."""

    def addToolBar(self, toolbar):
        """Add a toolbar to the viewport."""

    @property
    def imageItem(self) -> VardaImageItem:
        """Get the ImageRegionItem for this viewport."""
        ...

    @property
    def imageEntity(self) -> Image:
        """Get the Image entity for this viewport."""
        ...

    @property
    def viewBox(self) -> pg.ViewBox:
        """Get the ViewBox for this viewport."""
        ...

    @property
    def graphicsScene(self):
        """Get the GraphicsScene for this viewport."""
        ...
