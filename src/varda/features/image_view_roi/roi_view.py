# standard library
from typing import override

# third-party imports
import pyqtgraph as pg
from PyQt6.QtWidgets import (
    QVBoxLayout,
    QWidget,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
)
from PyQt6.QtCore import Qt, QTimer

# local imports
from varda.features.shared.selection_controls import StretchSelector
from .roi_viewmodel import ROIViewModel


class ROIView(QWidget):
    def __init__(self, viewModel: ROIViewModel, parent=None):
        super().__init__(parent)
        self.viewModel = viewModel
        self.viewModel.setView(self)  # <-- Important!
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(
            ["Index", "Color", "Slice Shape", "Actions"]
        )
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

        self.draw_roi_button = QPushButton("Draw ROI", self)

        layout = QVBoxLayout()
        layout.addWidget(self.draw_roi_button)
        layout.addWidget(self.table)
        self.setLayout(layout)

        self.table.cellClicked.connect(self._onTableRowClicked)
        self.draw_roi_button.clicked.connect(self._onDrawROIClicked)

    def updateROITable(self, rois):
        self.table.setRowCount(0)
        for i, roi in enumerate(rois):
            self.table.insertRow(i)
            self.table.setItem(i, 0, QTableWidgetItem(str(i)))
            self.table.setItem(i, 1, QTableWidgetItem(str(roi.color)))
            self.table.setItem(i, 2, QTableWidgetItem(str(roi.arraySlice.shape)))
            self._addPlotButtonToTable(i, roi)

    def _addPlotButtonToTable(self, row, roi):
        button = QPushButton("Plot", self)
        button.clicked.connect(lambda: self.viewModel.plotMeanSpectrum(roi))
        self.table.setCellWidget(row, 3, button)

    def _onTableRowClicked(self, row, column):
        roi = self.viewModel.getROIForRow(row)
        if roi:
            print(f"Clicked ROI: {roi}")

    def _onDrawROIClicked(self):
        self.viewModel.startDrawingROI()
