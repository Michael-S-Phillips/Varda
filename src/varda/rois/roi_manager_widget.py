import logging

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QSplitter, QPushButton

from varda.utilities.roi_utils import ROIStatistics
from varda.image_rendering.raster_view import (
    ROIDisplayController,
)
from varda.rois.roi_property_editor import ROIPropertyEditor
from varda.rois.roi_statistics_dialog import ROIStatisticsDialog
from varda.rois.roi_table_model import ROITableModel
from varda.rois.roi_table_view import ROITableView


logger = logging.getLogger(__name__)


class ROIManagerWidget(QWidget):
    def __init__(self, projContext, imageIndex=0, parent=None):
        super().__init__(parent)
        self.proj = projContext
        self.roiManager = projContext.roiManager
        self.model = ROITableModel(self.roiManager, imageIndex)
        self.table = ROITableView(self.model)
        self.propEditor = ROIPropertyEditor(self.roiManager)

        self.displayController = ROIDisplayController()

        # controls
        self.showAllBtn = QPushButton("Show All")
        self.hideAllBtn = QPushButton("Hide All")
        self.blinkBtn = QPushButton("Blink")
        self.blinkBtn.setCheckable(True)

        self.statsButton = QPushButton("View Statistics")
        self.statsButton.clicked.connect(self._showStats)

        # Layout
        splitter = QSplitter(self)
        splitter.addWidget(self.table)
        splitter.addWidget(self.propEditor)

        layout = QVBoxLayout(self)
        layout.addWidget(self.showAllBtn)
        layout.addWidget(self.hideAllBtn)
        layout.addWidget(self.blinkBtn)
        layout.addWidget(self.statsButton)
        layout.addWidget(splitter)

        # -- wire signals to displayController --
        # whenever ROI data changes, re-draw
        self.roiManager.sigROIAdded.connect(self._refreshDisplay)
        self.roiManager.sigROIUpdated.connect(self._refreshDisplay)
        self.roiManager.sigROIRemoved.connect(self._refreshDisplay)

        # show, hide, blink
        self.showAllBtn.clicked.connect(lambda: self._setAllVisibility(True))
        self.hideAllBtn.clicked.connect(lambda: self._setAllVisibility(False))
        self.blinkBtn.toggled.connect(self._toggleBlink)

        # highlight on selection
        self.table.selectionModel().selectionChanged.connect(self._onSelectionChanged)

        # Wire selection → editor
        selModel = self.table.selectionModel()
        selModel.selectionChanged.connect(self._onSelectionChanged)

        # Wire double-click → plot or whatever
        self.table.roiDoubleClicked.connect(self._onDoubleClicked)

    def getDisplayController(self) -> ROIDisplayController:
        """Get the ROI display controller for external registration of viewports."""
        return self.displayController

    def _refreshDisplay(self, *args):
        """Fetch current ROIs for this image and hand them off to your controller."""
        rois = self.roiManager.getROIsForImage(self.model.imageIndex)
        self.displayController.displayRoisForImage(rois)

    def _onSelectionChanged(self, selected, _):
        """When user picks one row, highlight that ROI in the viewport."""
        if not selected.indexes():
            return
        row = selected.indexes()[0].row()
        roi = self.model.rois()[row]
        self.displayController.highlightRoi(roi.id)
        # also let property editor know
        self.propEditor.setRoi(roi)

    def _setAllVisibility(self, visible: bool):
        """Show or hide every ROI via your manager → controller."""
        for roi in self.roiManager.getROIsForImage(self.model.imageIndex):
            self.roiManager.updateROI(roi.id, visible=visible)
        self._refreshDisplay()

    def _toggleBlink(self, blinkOn: bool):
        if blinkOn:
            self.displayController.startBlinking()
        else:
            self.displayController.stopBlinking()

    def _onDoubleClicked(self, roiId):
        # delegate to your existing ViewModel.pl​otRoiSpectrum(roiId)
        ...

    def _showStats(self):
        idxs = self.table.selectionModel().selectedRows()
        if not idxs:
            return
        roi = self.model.rois()[idxs[0].row()]
        image = self.proj.getImage(self.model.imageIndex)
        stats = ROIStatistics(roi, image)
        dlg = ROIStatisticsDialog(stats, self)
        dlg.exec()
