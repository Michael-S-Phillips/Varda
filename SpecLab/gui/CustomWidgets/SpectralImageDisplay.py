"""
SpectralImageDisplay.py
"""
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from SpecLab.gui.CustomWidgets import BasicWidget
import numpy as np


class SpectralImageDisplay(BasicWidget):

    def __init__(self):
        # super(SpectralImageDisplay, self).__init__()
        #
        # self.label = QLabel
        # self.npArray = np.ones((512, 512, 3))
        # self.image = QImage()
        # self.label.setPixmap(QPixmap(self.image))
        pass
    def setImage(img: np.ndarray):
        pass
