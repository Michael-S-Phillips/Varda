"""
customwidgets/SpecNavigationToolbar.py
An extension of the matplotlib NavigationToolbar2Qt widget that adds additional functionality for SpecLab,
as well as custom styling.
"""
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from pathlib import Path


class SpecNavigationToolbar(NavigationToolbar):
    def __init__(self, canvas, parent=None, coordinates=True):
        super().__init__(canvas, parent, coordinates)
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
