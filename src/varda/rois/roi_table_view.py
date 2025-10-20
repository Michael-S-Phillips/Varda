import logging

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QTableView

from varda.rois.delegates import ColorDelegate
from varda.rois.roi_table_model import ROITableModel

logger = logging.getLogger(__name__)


class ROITableView(QTableView):
    roiDoubleClicked = pyqtSignal(str)  # emit ROI id

    def __init__(self, model: ROITableModel, parent=None):
        super().__init__(parent)
        self.setModel(model)
        self.setSelectionBehavior(self.SelectionBehavior.SelectRows)
        self.setItemDelegateForColumn(3, ColorDelegate(self))
        self.doubleClicked.connect(self._onDoubleClick)

    def _onDoubleClick(self, index):
        roi = self.model()._rois()[index.row()]
        logger.debug(f"ROI {roi.id} double clicked")
        self.roiDoubleClicked.emit(roi.id)
