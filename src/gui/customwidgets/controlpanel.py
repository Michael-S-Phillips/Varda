from gui import maingui

from PyQt6 import QtCore, QtGui, QtWidgets
from PyQt6.QtGui import QAction
import pyqtgraph as pg
from gui.customwidgets import TextWidget
from pathlib import Path
import sys
import os

'''
Creates the right hand side control panel of the GUI
Will house the functionality to manipulate / yeild data
from the image
'''

class ControlPanel(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(ControlPanel, self).__init__(parent)
    

        self.tabsDock = QtWidgets.QDockWidget("Tabs", self)
        self.tabWidget = QtWidgets.QTabWidget()

        self.controls = QtWidgets.QMenu("Controls and Actions")
        self.tabWidget.addTab(self.controls, "Controls")
        self.menuButton = QtWidgets.QMenu(self)
        self.tabWidget.addTab(TextWidget("Adjust Settings"), "Settings")
        self.tabWidget.addTab(TextWidget("View Logs"), "Logs")
        self.tabsDock.setWidget(self.tabWidget)