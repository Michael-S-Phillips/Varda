"""Simplified ROI manager widget: table + basic controls."""

from __future__ import annotations

import logging

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
)

from varda.rois.roi_collection import ROICollection
from varda.rois.roi_table_model import ROITableModel
from varda.rois.roi_table_view import ROITableView

logger = logging.getLogger(__name__)


class ROIManagerWidget(QWidget):
    """Widget for managing ROIs: shows a table and delete button."""

    sigSelectionChanged = pyqtSignal(object)  # emits fid (int) or None
    sigPlotRequested = pyqtSignal(int)  # emits fid

    def __init__(
        self,
        collection: ROICollection,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._collection = collection

        # Model / View
        self._model = ROITableModel(collection, parent=self)
        self._table = ROITableView(self._model, parent=self)

        # Buttons
        self._deleteBtn = QPushButton("Delete Selected")
        self._deleteBtn.clicked.connect(self._deleteSelected)

        self._exportBtn = QPushButton("Export...")
        self._exportBtn.clicked.connect(self._exportCollection)

        self._plotBtn = QPushButton("Plot Spectrum")
        self._plotBtn.clicked.connect(self._plotSelected)
        self._plotBtn.setEnabled(False)

        # Layout
        btnRow = QHBoxLayout()
        btnRow.addWidget(self._deleteBtn)
        btnRow.addWidget(self._exportBtn)
        btnRow.addWidget(self._plotBtn)
        btnRow.addStretch()

        layout = QVBoxLayout(self)
        layout.addLayout(btnRow)
        layout.addWidget(self._table)

        # Forward table selection changes as fid
        selModel = self._table.selectionModel()
        if selModel is not None:
            selModel.selectionChanged.connect(self._onSelectionChanged)

    @property
    def table(self) -> ROITableView:
        return self._table

    @property
    def model(self) -> ROITableModel:
        return self._model

    def selectedFid(self) -> int | None:
        """Return the fid of the currently selected row, or None."""
        idxs = self._table.selectionModel().selectedRows()
        if not idxs:
            return None
        return self._model.fidForRow(idxs[0].row())

    def _onSelectionChanged(self, selected, _deselected) -> None:
        if not selected.indexes():
            self.sigSelectionChanged.emit(None)
            self._plotBtn.setEnabled(False)
            return
        fid = self._model.fidForRow(selected.indexes()[0].row())
        self.sigSelectionChanged.emit(fid)
        self._plotBtn.setEnabled(fid is not None)

    def _plotSelected(self) -> None:
        fid = self.selectedFid()
        if fid is not None:
            self.sigPlotRequested.emit(fid)

    def _deleteSelected(self) -> None:
        fid = self.selectedFid()
        if fid is not None:
            self._collection.removeROI(fid)

    def _exportCollection(self) -> None:
        from PyQt6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export ROIs",
            "",
            "GeoJSON (*.geojson);;GeoPackage (*.gpkg);;Shapefile (*.shp)",
        )
        if path:
            self._collection.toFile(path)
