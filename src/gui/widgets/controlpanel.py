from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QMenu,
    QPushButton,
    QDockWidget,
    QTabWidget,
    QLabel,
)
from PyQt6.QtCore import Qt, QPoint, QEvent
import sys


class ControlPanel(QWidget):
    # this is the control panel that appears on the top right of the GUI. It holds an instance of imageWorkspace
    # so you can access functions from there for each control option
    def __init__(self, imageIndex, parent=None):
        super(ControlPanel, self).__init__(parent)
        self.imageIndex = imageIndex
        self.tabsDock = QDockWidget("Tabs", self)
        self.tabWidget = QTabWidget()

        # Dropdown button
        self.button = QPushButton("Select")
        main_layout = QVBoxLayout()

        # Main container

        # Define secondary menu options and initialize dropdown menus with event handler
        # Add any new control options or setting options here, and update the handle_menu_action function
        menu = QMenu()
        roi_menu = QMenu("ROI", self)
        roi_menu.addAction("Draw ROI", lambda: print("drawing roi"))

        plots_menu = QMenu("Plots", self)
        plots_menu.addAction("Show pixel plot", lambda: print("pixel plot"))
        settings_menu = QMenu("Settings", self)

        menu.addMenu(roi_menu)
        menu.addMenu(plots_menu)
        menu.addMenu(settings_menu)

        self.button.setMenu(menu)

        self.tabsDock.setWidget(self.button)

        # Main layout for ControlPanel
        main_layout.addWidget(self.tabsDock)
        self.setLayout(main_layout)
