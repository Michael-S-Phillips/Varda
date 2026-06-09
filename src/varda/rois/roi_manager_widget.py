"""ROI manager widget: table + controls, owning ROI plotting + denominator state."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QCheckBox,
    QPushButton,
    QInputDialog,
    QMessageBox,
)

from shapely.geometry import Polygon

from varda.image_loading.crism_geometry import (
    computeColumnLockedTranslation,
    loadColumnGeometry,
    resolveGeometryFile,
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
    sigTemplateChanged = pyqtSignal(object)  # emits fid (int) or None

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
        self._templateFid: int | None = None

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

        # "Lock to sensor column" toggle for template placement, enabled only
        # when a CRISM DDR geometry companion resolves for this image.
        self._lockColumnCheck = QCheckBox("Lock to sensor column")
        hasDdr = bool(image.filePath) and resolveGeometryFile(image.filePath) is not None
        self._lockColumnCheck.setEnabled(hasDdr)
        if not hasDdr:
            self._lockColumnCheck.setToolTip("No CRISM DDR geometry found for this image")

        # Layout
        btnRow = QHBoxLayout()
        btnRow.addWidget(self._deleteBtn)
        btnRow.addWidget(self._addColumnBtn)
        btnRow.addWidget(self._exportBtn)
        btnRow.addWidget(self._plotBtn)
        btnRow.addWidget(self._lockColumnCheck)
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
        self._table.sigTemplateSetRequested.connect(self.setTemplate)
        self._table.sigTemplateClearRequested.connect(lambda: self.setTemplate(None))

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

    @property
    def templateFid(self) -> int | None:
        return self._templateFid

    @property
    def lockColumn(self) -> bool:
        """Whether template placement should snap to the same sensor column."""
        return self._lockColumnCheck.isChecked()

    def setTemplate(self, fid: int | None) -> None:
        """Set (or clear, with None) the ROI used as a placement template."""
        if fid == self._templateFid:
            return
        self._templateFid = fid
        self._model.setTemplateFid(fid)
        self.sigTemplateChanged.emit(fid)

    def placeTemplate(self, clickRow: int, clickCol: int) -> None:
        """Stamp a copy of the template ROI centered on the clicked pixel.

        When ``self.lockColumn`` is set and a CRISM DDR resolves, the horizontal
        shift is chosen so the copy sits on the template's detector column;
        otherwise a plain centroid-to-click translation is used.
        """
        if self._templateFid is None:
            QMessageBox.information(
                self,
                "No template set",
                "Right-click an ROI and choose 'Set as Template' first, then "
                "right-click the image to place a copy.",
            )
            return

        template = self._collection.getROI(self._templateFid)
        pixelCoords = self._collection.getPixelCoordinates(
            self._templateFid
        )  # (N,2) col,row
        srcCx = float(pixelCoords[:, 0].mean())
        srcCy = float(pixelCoords[:, 1].mean())
        dx = float(clickCol) - srcCx
        dy = float(clickRow) - srcCy

        if self.lockColumn:
            colGeom = (
                loadColumnGeometry(self._image.filePath)
                if self._image.filePath
                else None
            )
            if colGeom is not None:
                locked = computeColumnLockedTranslation(
                    pixelCoords, clickRow=clickRow, clickCol=clickCol, geometry=colGeom
                )
                if locked is not None:
                    dx, dy = locked

        newPixels = pixelCoords + np.array([dx, dy])
        if self._image.hasGeospatialData:
            geoCoords = [
                self._image.pixelToGeo(int(round(c)), int(round(r)))
                for c, r in newPixels
            ]
            geometry = Polygon(geoCoords)
        else:
            geometry = Polygon(newPixels)

        self._collection.addROI(
            geometry=geometry,
            name=f"{template.name} copy",
            color=template.color,
            roiType=template.roiType,
        )

    def plotSpectrum(self, fid: int) -> None:
        """Plot the mean spectrum of an ROI, shaded with a +/- std-dev band."""
        stats = self._collection.getROIStatistics(fid, self._image)
        if stats["pixel_count"] == 0:
            logger.warning("ROI fid=%d has no pixels", fid)
            return
        mean = np.asarray(stats["mean"])
        std = np.asarray(stats["std"])
        wavelengths = VardaPlotWidget.getPlottableWavelengths(self._image, len(mean))
        roi = self._collection.getROI(fid)

        fillColor = roi.color.toQColor()
        fillColor.setAlpha(50)
        self._plotWidget.plotWithFill(
            wavelengths,
            mean,
            yLower=mean - std,
            yUpper=mean + std,
            fillBrush=pg.mkBrush(fillColor),
            color=roi.color,
            name=roi.name,
        )

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
        if fid == self._templateFid:
            self.setTemplate(None)

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
