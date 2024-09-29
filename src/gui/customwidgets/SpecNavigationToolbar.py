"""
customwidgets/SpecNavigationToolbar.py
An extension of the matplotlib NavigationToolbar2Qt widget that adds additional functionality for SpecLab,
as well as custom styling.
"""
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.backend_managers import ToolManager as tm
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from pathlib import Path


class SpecNavigationToolbar(NavigationToolbar):
    def __init__(self, imageViewer, parent=None, coordinates=True):
      super().__init__(imageViewer, parent, coordinates)
      self.setStyleSheet("""
      QToolBar {
         background-color: #f0f0f0;
         border: 1px solid #ccc;
      }
      QToolButton {
         background-color: #e0e0e0;
         border: 1px solid #ccc;
         padding: 5px;
      }
      QToolButton:hover {
         background-color: #b0b0b0;
      }
      """)
      # example of replacing an icon

      for action in self.actions():
         if action.text() == "Pan":
            action.setIcon(QIcon(str(Path("./resources/hi.png"))))
         if action.text() == "Home":
            action.setIcon(QIcon(str(Path("./resources/reset.png"))))
         if action.text() == "Zoom":
            action.setIcon(QIcon(str(Path("./resources/zoom_select.png"))))
         if action.text() == "Back" or action.text() == "Forward" or \
            action.text() == "Subplots" or action.text() == "Customize":
            self.removeAction(action)

      self.setIconSize(QSize(20, 20))



            
