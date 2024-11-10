# standard library
from typing import override

# Third-party
import pyqtgraph as pg
from PyQt6 import QtCore, QtGui, QtWidgets
# local imports
import debug

class TripleImageHistogram(pg.HistogramLUTItem):
    def __init__(self, mainImage, contextImage, zoomImage, **kwargs):
        super().__init__(mainImage, **kwargs)
        self.contextHistogram = pg.HistogramLUTItem(contextImage, **kwargs)
        self.zoomHistogram = pg.HistogramLUTItem(zoomImage, **kwargs)


    @override
    def regionChanging(self):
        profile = debug.Profiler()
        super().regionChanging()
        self.contextHistogram.imageItem().setLevels(self.getLevels())
        self.zoomHistogram.imageItem().setLevels(self.getLevels())
        profile("Time to Update Histogram Levels")
