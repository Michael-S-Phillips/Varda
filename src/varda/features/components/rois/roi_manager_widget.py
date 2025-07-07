import logging

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QSplitter, QPushButton

import varda.app
from varda.app.services.roi_utils import ROIStatistics
from varda.features.components.rois.roi_property_editor import ROIPropertyEditor
from varda.features.components.rois.roi_statistics_dialog import ROIStatisticsDialog
from varda.features.components.rois.roi_table_model import ROITableModel
from varda.features.components.rois.roi_table_view import ROITableView


logger = logging.getLogger(__name__)


class ROIManagerWidget(QWidget):
    def __init__(self, projContext, imageIndex=0, parent=None):
        super().__init__(parent)
        self.roiManager = projContext.roiManager
        self.model = ROITableModel(self.roiManager, imageIndex)
        self.table = ROITableView(self.model)
        self.propEditor = ROIPropertyEditor(self.roiManager)

        # Buttons
        self.statsButton = QPushButton("View Statistics")
        self.statsButton.clicked.connect(self._showStats)

        # Layout
        splitter = QSplitter(self)
        splitter.addWidget(self.table)
        splitter.addWidget(self.propEditor)

        layout = QVBoxLayout(self)
        layout.addWidget(self.statsButton)
        layout.addWidget(splitter)

        # Wire selection → editor
        selModel = self.table.selectionModel()
        selModel.selectionChanged.connect(self._onSelectionChanged)

        # Wire double-click → plot or whatever
        self.table.roiDoubleClicked.connect(self._onDoubleClicked)

    def _onSelectionChanged(self, selected, deselected):
        idx = selected.indexes()[0]
        roi = self.model._rois()[idx.row()]
        self.propEditor.setRoi(roi)

    def _onDoubleClicked(self, roiId):
        # delegate to your existing ViewModel.pl​otRoiSpectrum(roiId)
        ...

    def _showStats(self):
        idxs = self.table.selectionModel().selectedRows()
        if not idxs:
            return
        roi = self.model._rois()[idxs[0].row()]
        image = varda.app.proj.getImage(self.model.imageIndex)
        stats = ROIStatistics(roi, image)
        dlg = ROIStatisticsDialog(stats, self)
        dlg.exec()
