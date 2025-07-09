from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDockWidget


class VardaDockWidget(QDockWidget):
    def __init__(self, title, widget=None, parent=None):
        super().__init__(title, parent)
        self.setObjectName("VardaDockWidget")
        self.setFeatures(
            self.DockWidgetFeature.DockWidgetMovable
            | self.DockWidgetFeature.DockWidgetFloatable
        )
        self.setAllowedAreas(Qt.DockWidgetArea.AllDockWidgetAreas)
        if widget:
            self.setWidget(widget)
