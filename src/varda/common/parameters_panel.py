from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget, QFormLayout

class PropertiesPanel(QWidget):
    sigParametersChanged = pyqtSignal()
    def __init__(self, continuousUpdates=True, parameters=None):
        super().__init__()
        self.form = QFormLayout
        self.parameters = parameters
