from speclabgui import maingui

from PyQt6 import QtCore, QtGui, QtWidgets
import pyqtgraph as pg
from speclabgui.customwidgets import TextWidget
from pathlib import Path
import sys
import os

'''
Creates the right hand side control panel of the GUI
Will house the functionality to manipulate / yeild data
from the image
'''

class ControlPanel(QtWidgets.QWidget):
    def __init__(self):
        super(ControlPanel, self).__init__()

        self.tabsDock = QtWidgets.QDockWidget("Tabs", self)
        tabWidget = QtWidgets.QTabWidget()
        tabWidget.addTab(TextWidget("Controls and Actions"), "Control Panel")
        tabWidget.addTab(TextWidget("Adjust Settings"), "Settings")
        tabWidget.addTab(TextWidget("View Logs"), "Logs")
        self.tabsDock.setWidget(tabWidget)
