from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtWidgets import QPushButton
from pyqtgraph import ROI

class RoiRegion(ROI):

    id = 1
    def __init__(self, roi):
        super().__init__(roi)

        self.roi = roi
        self.id = id
        id += 1
        self.comments = ""
        self.meanSpecPlot = QPushButton("Load Mean", self)
        self.stdSpecPlot = QPushButton("Load Std", self)

        

