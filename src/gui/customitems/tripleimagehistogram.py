# standard library
from typing import override

# Third-party
import pyqtgraph as pg
from PyQt6 import QtCore, QtGui, QtWidgets
# local imports
import debug

class TripleImageHistogram(pg.HistogramLUTItem):
    """
    Allows us to control the levels of three images via a single histogram
    """
    def __init__(self, mainImage, contextImage, zoomImage, **kwargs):
        super().__init__(contextImage, **kwargs)
        self.mainImageHistogram = pg.HistogramLUTItem(mainImage, **kwargs)
        self.zoomHistogram = pg.HistogramLUTItem(zoomImage, **kwargs)

    @override
    def regionChanging(self):
        """
        override of the regionChanging method to update the levels of all three images
        """
        profile = debug.Profiler()
        super().regionChanging()
        self.mainImageHistogram.imageItem().setLevels(self.getLevels())
        self.zoomHistogram.imageItem().setLevels(self.getLevels())
        profile("Time to Update Histogram Levels")
