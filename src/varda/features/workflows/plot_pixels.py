from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QWidget

from varda.features.components.raster_view import IViewport, PixelSelectTool

class PlotPixels(QObject):
    def __init__(self, viewport: IViewport, parent=None):
        super().__init__(parent)
        self.viewport = viewport
        self.pixelSelector = PixelSelectTool(self.viewport, self)
        self.pixelSelector.sigPixelSelected.connect(self._onPixelSelected)

    def _onPixelSelected(self, point):
        pass