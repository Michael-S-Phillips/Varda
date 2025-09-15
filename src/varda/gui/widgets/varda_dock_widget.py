from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDockWidget, QMainWindow


class VardaDockWidget(QDockWidget):
    def __init__(self, title, widget=None, area=None, parent=None):
        super().__init__(title, parent)

        self.setObjectName("VardaDockWidget")
        self.setFeatures(
            self.DockWidgetFeature.DockWidgetMovable
            | self.DockWidgetFeature.DockWidgetFloatable
        )
        self.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        if widget:
            self.setWidget(widget)

        if parent is not None and area is not None and isinstance(parent, QMainWindow):
            parent.addDockWidget(area, self)
