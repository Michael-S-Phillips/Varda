# standard library
from typing import override

# third-party imports
import pyqtgraph as pg
from PyQt6.QtWidgets import QVBoxLayout, QWidget, QTableWidget, QTableWidgetItem, QPushButton
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
        self.table.setHorizontalHeaderLabels(["ROI index", "Color", "Plot mean spectrum", "Data3"])

        self.draw_roi_button = QPushButton("Draw ROI", self)

        layout = QVBoxLayout()
        layout.addWidget(self.draw_roi_button)
        layout.addWidget(self.table)
        self.setLayout(layout)

        # Associate the table with the view model
        self.table.cellClicked.connect(self._onTableRowClicked)
        self.draw_roi_button.clicked.connect(self._onDrawROIClicked)

    def _onTableRowClicked(self, row, column):
        """
        Handle table row clicks and retrieve the associated ROI.
        """
        roi = self.viewModel.getROIForRow(row)
        if roi:
            print(f"Clicked ROI: {roi}")
            # Return or use the FreeHandROI object as needed

    def _onDrawROIClicked(self):
        """Handle the 'Draw ROI' button click."""
        self.viewModel.startDrawingROI()

    def _addPlotButtonToTable(self, row, roi):
        """
        Add a "Plot mean spectrum" button to the specified table row.

        Args:
            row (int): The row index to add the button to.
            roi (FreeHandROI): The associated ROI for this row.
        """
        button = QPushButton("Plot", self)
        button.clicked.connect(lambda: self.viewModel.plotMeanSpectrum(roi))
        self.table.setCellWidget(row, 2, button)

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

