# standard library
from typing import override

# third-party imports
import pyqtgraph as pg
from PyQt6.QtWidgets import QVBoxLayout, QWidget, QTableWidget, QTableWidgetItem
from PyQt6.QtCore import Qt, QTimer

# local imports
from features.shared.selection_controls import StretchSelector
from .roi_viewmodel import ROIViewModel


class ROIView(QWidget):
    def __init__(self, viewModel: ROIViewModel, parent=None):
        super().__init__(parent)
        self.viewModel = viewModel
        self.table = QTableWidget(self)

        # Set up the table widget
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ROI index", "Data1", "Data2", "Data3"])

        layout = QVBoxLayout()
        layout.addWidget(self.table)
        self.setLayout(layout)

        # Associate the table with the view model
        self.viewModel.setROITable(self.table)

    def _connectSignals(self):
        pass
        # self.viewModel.sigBandChanged.connect(self._onBandChanged)
        # self.bandSelector.currentIndexChanged.connect(self.viewModel.selectBand)
        # self.rBandSlider.sigPositionChanged.connect(
        #     lambda: self.viewModel.updateBand(r=self.rBandSlider.value())
        # )
        # self.gBandSlider.sigPositionChanged.connect(
        #     lambda: self.viewModel.updateBand(g=self.gBandSlider.value())
        # )
        # self.bBandSlider.sigPositionChanged.connect(
        #     lambda: self.viewModel.updateBand(b=self.bBandSlider.value())
        # )

