"""ROI manager widget: table + controls, owning ROI plotting + denominator state."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QInputDialog,
    QMessageBox,
)

from varda.plotting.plot import VardaPlotWidget
from varda.rois.roi_collection import ROICollection
from varda.rois.roi_table_model import ROITableModel
from varda.rois.roi_table_view import ROITableView

if TYPE_CHECKING:
    from varda.common.entities import VardaRaster

logger = logging.getLogger(__name__)


class ROIManagerWidget(QWidget):
    """Table + controls for ROIs. Owns spectral plotting and denominator state.

    The workspace supplies the spectral ``image`` and the ``plotWidget`` to draw
    into; this widget computes mean and ratio spectra and plots them directly, so
    the plotting logic is not duplicated across workspaces.
    """

    sigSelectionChanged = pyqtSignal(object)  # emits fid (int) or None
    sigDenominatorChanged = pyqtSignal(object)  # emits fid (int) or None

    def __init__(
        self,
        collection: ROICollection,
        image: VardaRaster,
        plotWidget: VardaPlotWidget,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._collection = collection
        self._image = image
        self._plotWidget = plotWidget
        self._denominatorFid: int | None = None

        # Model / View
        self._model = ROITableModel(collection, parent=self)
        self._table = ROITableView(self._model, parent=self)

        # Buttons
        self._deleteBtn = QPushButton("Delete Selected")
        self._deleteBtn.clicked.connect(self._deleteSelected)

        self._addColumnBtn = QPushButton("Add Column...")
        self._addColumnBtn.clicked.connect(self._addColumn)

        self._exportBtn = QPushButton("Export...")
        self._exportBtn.clicked.connect(self._exportCollection)

        self._plotBtn = QPushButton("Plot Spectrum")
        self._plotBtn.clicked.connect(self._plotSelected)
        self._plotBtn.setEnabled(False)

        # Layout
        btnRow = QHBoxLayout()
        btnRow.addWidget(self._deleteBtn)
        btnRow.addWidget(self._addColumnBtn)
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

        # Wire row context-menu actions
        self._table.sigPlotSpectrumRequested.connect(self.plotSpectrum)
        self._table.sigPlotRatioRequested.connect(self.plotRatioSpectrum)
        self._table.sigDenominatorSetRequested.connect(self.setDenominator)
        self._table.sigDenominatorClearRequested.connect(
            lambda: self.setDenominator(None)
        )

        # Keep denominator state consistent if its ROI is deleted
        collection.sigROIRemoved.connect(self._onROIRemoved)

    @property
    def table(self) -> ROITableView:
        return self._table

    @property
    def model(self) -> ROITableModel:
        return self._model

    @property
    def denominatorFid(self) -> int | None:
        return self._denominatorFid

    def selectedFid(self) -> int | None:
        """Return the fid of the currently selected row, or None."""
        idxs = self._table.selectionModel().selectedRows()
        if not idxs:
            return None
        return self._model.fidForRow(idxs[0].row())

    # --- Plotting / ratio ---

    def setDenominator(self, fid: int | None) -> None:
        """Set (or clear, with None) the ratio reference ROI."""
        if fid == self._denominatorFid:
            return
        self._denominatorFid = fid
        self._model.setDenominatorFid(fid)
        self.sigDenominatorChanged.emit(fid)

    def plotSpectrum(self, fid: int) -> None:
        """Plot the mean spectrum of an ROI into the plot widget."""
        stats = self._collection.getROIStatistics(fid, self._image)
        if stats["pixel_count"] == 0:
            logger.warning("ROI fid=%d has no pixels", fid)
            return
        mean = np.asarray(stats["mean"])
        wavelengths = VardaPlotWidget.getPlottableWavelengths(self._image, len(mean))
        roi = self._collection.getROI(fid)
        self._plotWidget.plot(wavelengths, mean, color=roi.color, name=roi.name)

    def plotRatioSpectrum(self, fid: int) -> None:
        """Plot an ROI's mean spectrum divided by the denominator's mean."""
        if self._denominatorFid is None:
            QMessageBox.information(
                self,
                "No denominator set",
                "Right-click an ROI and choose 'Set as Denominator' first, "
                "then plot a ratio spectrum.",
            )
            return
        ratio = self._collection.getRatioSpectrum(
            fid, self._denominatorFid, self._image
        )
        numerator = self._collection.getROI(fid)
        denominator = self._collection.getROI(self._denominatorFid)
        wavelengths = VardaPlotWidget.getPlottableWavelengths(
            self._image, len(ratio.values)
        )
        self._plotWidget.plot(
            wavelengths,
            ratio.values,
            color=numerator.color,
            name=f"{numerator.name} / {denominator.name}",
        )

    # --- Internal handlers ---

    def _onSelectionChanged(self, selected, _deselected) -> None:
        if not selected.indexes():
            self.sigSelectionChanged.emit(None)
            self._plotBtn.setEnabled(False)
            return
        fid = self._model.fidForRow(selected.indexes()[0].row())
        self.sigSelectionChanged.emit(fid)
        self._plotBtn.setEnabled(fid is not None)

    def _onROIRemoved(self, fid: int) -> None:
        if fid == self._denominatorFid:
            self.setDenominator(None)

    def _plotSelected(self) -> None:
        fid = self.selectedFid()
        if fid is not None:
            self.plotSpectrum(fid)

    def _deleteSelected(self) -> None:
        fid = self.selectedFid()
        if fid is not None:
            self._collection.removeROI(fid)

    def _addColumn(self) -> None:
        name, ok = QInputDialog.getText(self, "Add Column", "Column name:")
        if not ok or not name.strip():
            return
        try:
            self._collection.addColumn(name)
        except ValueError as e:
            QMessageBox.warning(self, "Cannot Add Column", str(e))

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
