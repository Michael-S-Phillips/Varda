from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QMenu, QMessageBox, QDockWidget, QTabWidget, QLabel
from PyQt6.QtCore import Qt, QPoint, QEvent
import sys


class DropdownMenu(QMenu):
    # subclass for controlPanel, creates a dropdown menu inside a dropdown menu
    # for the controls panel
    def __init__(self, options, event_handler, parent=None):
        super().__init__(parent)
        self.options = options
        self.event_handler = event_handler
        self.create_menu()

    def create_menu(self):
        for index, item in enumerate(self.options.keys()):
            action = QAction(item, self)
            action.hovered.connect(lambda checked=False, idx=index, text=item: self.show_secondary_menu(idx, text))
            self.addAction(action)

    def show_secondary_menu(self, index, option_text):
        secondary_menu = QMenu(self)
        for action_text in self.options[option_text]:
            action = QAction(action_text, self)
            action.triggered.connect(lambda checked, text=action_text: self.event_handler(option_text, text))
            secondary_menu.addAction(action)

        main_menu_position = self.geometry().topRight()
        secondary_menu_position = main_menu_position + QPoint(0, index * self.actionGeometry(
            self.actions()[index]).height())
        secondary_menu.popup(secondary_menu_position)


class ControlPanel(QWidget):
    # this is the control panel that appears on the top right of the GUI. It holds an instance of imageWorkspace
    # so you can access functions from there for each control option
    def __init__(self, imageIndex, parent=None):
        super(ControlPanel, self).__init__(parent)
        self.imageIndex = imageIndex
        self.tabsDock = QDockWidget("Tabs", self)
        self.tabWidget = QTabWidget()
        

        # Define secondary menu options and initialize dropdown menus with event handler
        # Add any new control options or setting options here, and update the handle_menu_action function
        self.dropdown_menus = {
            "Controls": DropdownMenu(
                {"ROI Options": ["Poly ROI", "Save ROI", "Load ROI"], 
                 "Plots": ["Pixel Plot", "Avg Strength Plot"],
                 "Option 3": ["Action 3-1", "Action 3-2"]},
                self.handle_menu_action, self
            ),
            "Adjust Settings": DropdownMenu(
                {"Setting A": ["Sub-action A1", "Sub-action A2"], "Setting B": ["Sub-action B1", "Sub-action B2"]},
                self.handle_menu_action, self
            ),
            "View Logs": DropdownMenu(
                {"Log 1": ["Detail 1", "Detail 2"], "Log 2": ["Detail 3", "Detail 4"]},
                self.handle_menu_action, self
            ),
        }

        # Add tabs with empty content; dropdown menu will trigger on tab clicks
        self.tabWidget.addTab(QWidget(), "Controls")
        self.tabWidget.addTab(QWidget(), "Adjust Settings")
        self.tabWidget.addTab(QWidget(), "View Logs")

        # Set up event filter to capture tab clicks
        self.tabWidget.tabBar().installEventFilter(self)
        self.tabsDock.setWidget(self.tabWidget)

        # Main layout for ControlPanel
        main_layout = QVBoxLayout()
        main_layout.addWidget(self.tabsDock)
        self.setLayout(main_layout)

    def eventFilter(self, source, event):
        if source == self.tabWidget.tabBar() and event.type() == QEvent.Type.MouseButtonPress:
            tab_index = self.tabWidget.tabBar().tabAt(event.pos())
            tab_text = self.tabWidget.tabText(tab_index)
            if tab_text in self.dropdown_menus:
                self.show_dropdown_menu(tab_text)
        return super().eventFilter(source, event)

    def show_dropdown_menu(self, tab_text):
        menu = self.dropdown_menus[tab_text]
        tab_position = self.tabWidget.tabBar().mapToGlobal(
            self.tabWidget.tabBar().tabRect(self.tabWidget.currentIndex()).bottomLeft())
        menu.exec(tab_position)

    def handle_menu_action(self, primary_option, secondary_action):
        # load actions here for primary / secondary actions. Use methods in self.imgWorkspace
        # to access image data.
        if self.imgWorkspace.image is not None and primary_option == "ROI Options":
            if secondary_action == "Poly ROI":
                self.imgWorkspace.addPolylineROI()
            elif secondary_action == "Save ROI":
                self.imgWorkspace.saveROI()
            elif secondary_action == "Load ROI":
                self.imgWorkspace.loadROI()
        if self.imgWorkspace.image is not None and primary_option == "Plots":
            if secondary_action == "Pixel Plot":
                self.imgWorkspace.pixel_plot.show()
                self.imgWorkspace.plot.hide()
                self.imgWorkspace.ROIplot.hide()
            if secondary_action == "Avg Strength Plot":
                self.imgWorkspace.pixel_plot.hide()
                self.imgWorkspace.plot.show()
                self.imgWorkspace.ROIplot.hide()
        else:
            pass
