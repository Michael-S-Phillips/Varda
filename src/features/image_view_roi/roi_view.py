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
    """A view for viewing and selecting ROIs that have been drawn
    on the main rasterview"""

    viewModel: ROIViewModel
    widgetHeight = 300
    widgetWidth = 500
    updateTimer: QTimer

    def __init__(self, viewModel=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("ROIs for image" + str(viewModel.imageIndex))
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.WindowStaysOnTopHint)
        self.setMaximumHeight(self.widgetHeight)
        self.setMaximumWidth(self.widgetWidth)
        self.viewModel = viewModel

        self._initUI()
        self._connectSignals()
        self.show()

    def _initUI(self):
    # Create GraphicsLayout
        graphicsLayout = pg.GraphicsLayout()
        graphicsLayout.setContentsMargins(0, 0, 0, 0)
        graphicsLayout.setSpacing(0)

        # ViewBox setup
        vbox = pg.ViewBox()
        vbox.setContentsMargins(0, 0, 0, 0)
        graphicsLayout.addItem(vbox)

        # Create the table layout
        rois = self.viewModel.proj.getROIs(self.viewModel.imageIndex)
        num_rois = len(rois)
        num_columns = 4  # ROI index + 3 data columns
        column_labels = ["ROI index", "data1", "data2", "data3"]


        table = QTableWidget(num_rois, num_columns, self)
        table.setHorizontalHeaderLabels(column_labels)

        # Populate the table
        for row_index, roi in enumerate(rois):
            # ROI index
            table.setItem(row_index, 0, QTableWidgetItem(str(row_index)))

            # Example data population (replace with actual ROI data)
            table.setItem(row_index, 1, QTableWidgetItem("Value1"))
            table.setItem(row_index, 2, QTableWidgetItem("Value2"))
            table.setItem(row_index, 3, QTableWidgetItem("Value3"))

        # Adjust table settings
        table.resizeColumnsToContents()
        table.resizeRowsToContents()

        # Add the table to the layout
        layout = QVBoxLayout()
        layout.addWidget(table)
        self.setLayout(layout)

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

