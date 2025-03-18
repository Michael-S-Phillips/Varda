import time
import json
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QTreeWidget, QTreeWidgetItem, QLineEdit
from PyQt6.QtCore import Qt

DEBUG = True


class Profiler:  # pylint: disable=too-few-public-methods
    """
    A simple profiler to measure the time elapsed between two points in the code.

    Usage:
        profiler = Profiler()
        # Code to be profiled
        profiler("Part 1 elapsed") # Output - Part 1 time elapsed: 0.1234 ms
        # More code to be profiled
        profiler("Part 2 time elapsed") # Output - Part 2 time elapsed: 0.1234 ms
    """

    # Set this flag to True to disable the profiler
    DISABLE = False  # pylint: disable=invalid-name

    def __init__(self):
        """
        Initialize the profiler with the current time.
        """
        self.timeStarted = time.perf_counter()

    def __call__(self, *args):
        """
        Measure and print the time elapsed since the last call or initialization.

        If the DISABLE flag is set to True, the function will return without doing
        anything.

        @param:
            *args: Optional positional arguments. If provided, the first argument
            will be used as the message prefix.
        """
        if self.DISABLE:
            return
        timeElapsed = (time.perf_counter() - self.timeStarted) * 1000
        if len(args) > 0:
            print(f"{args[0]}: {timeElapsed: 0.4f} ms")
        else:
            print(f"Time elapsed: {timeElapsed: 0.4f} ms")
        self.timeStarted = time.perf_counter()




class ProjectContextDataTable(QWidget):
    """A debugging widget for displaying all project context data."""

    def __init__(self, proj, parent=None):
        super().__init__(parent)
        self.proj = proj
        self._initUI()
        self._connectSignals()
        self.show()

    def _initUI(self):
        self.setWindowTitle("Project Context Data")
        self.setWindowTitle("Project Context Data")
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        self.layout = QVBoxLayout(self)

        self.searchBox = QLineEdit(self)
        self.searchBox.setPlaceholderText("Search...")
        self.searchBox.textChanged.connect(self.filterTree)
        self.layout.addWidget(self.searchBox)

        self.treeWidget = QTreeWidget(self)
        self.treeWidget.setColumnCount(2)
        self.layout.addWidget(self.treeWidget)
        self.setLayout(self.layout)
        self.updateData()

    def _connectSignals(self):
        self.proj.sigDataChanged.connect(self.updateData)

    def updateData(self, changeType=None):
        """Update the tree widget with the current project context data."""
        self.treeWidget.clear()
        data = self.proj.serialize()
        self._populateTree(data, self.treeWidget.invisibleRootItem())



    def _populateTree(self, data, parent):
        """Recursively populate the tree widget with data."""
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    item = QTreeWidgetItem([key])
                    parent.addChild(item)
                    self._populateTree(value, item)
                else:
                    item = QTreeWidgetItem([key, str(value)])
                    parent.addChild(item)
        elif isinstance(data, list):
            for index, value in enumerate(data):
                if isinstance(value, (dict, list)):
                    item = QTreeWidgetItem([str(index)])
                    parent.addChild(item)
                    self._populateTree(value, item)
                else:
                    item = QTreeWidgetItem([f"{index} ({type(value)})", str(value)])
                    parent.addChild(item)

    def filterTree(self, text):
        """Filter the tree widget items based on the search text."""
        for i in range(self.treeWidget.topLevelItemCount()):
            item = self.treeWidget.topLevelItem(i)
            self._filterItem(item, text)

    def _filterItem(self, item, text):
        """Recursively filter the tree widget items."""
        match = text.lower() in item.text(0).lower() or text.lower() in item.text(1).lower()
        for i in range(item.childCount()):
            child = item.child(i)
            childMatch = self._filterItem(child, text)
            match = match or childMatch
        item.setHidden(not match)
        item.setExpanded(match)
        return match
