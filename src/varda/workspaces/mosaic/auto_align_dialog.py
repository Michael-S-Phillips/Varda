"""Auto Align: find tie points between the selected image and the images it
overlaps, fit them robustly, and show how each band agreed."""

from __future__ import annotations

import numpy as np
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from varda.common.ui import MutedLabel
from varda.mosaicking.bands import DEFAULT_BAND_COUNT
from varda.mosaicking.matching import (
    DEFAULT_TILE,
    AutoAlignResult,
    MatchMethod,
    MatchSettings,
)
from varda.mosaicking.model import DEFAULT_INLIER_PX, BandFit, MosaicProject

ALL_OVERLAPPING = -1
TILE_SIZES = (32, 64, 128)
BAND_COLUMNS = ["Band", "Wavelength", "SNR", "Points", "Kept", "RMS (px)", "Use"]


class AutoAlignDialog(QDialog):
    # (moving key, reference keys, settings, inlier threshold in px)
    sigRun = pyqtSignal(int, list, object, float)
    sigBandUsed = pyqtSignal(int, int, bool)  # (moving key, band, used)
    sigAddField = pyqtSignal(object)  # DisplacementField

    def __init__(
        self, project: MosaicProject, movingKey: int, parent: QWidget | None = None
    ):
        super().__init__(parent)
        self.project = project
        self.movingKey = movingKey
        self.alignment: AutoAlignResult | None = None
        moving = project.input(movingKey)
        self.setWindowTitle(f"Auto Align {moving.image.name}")
        self.setMinimumWidth(560)

        self.reference = QComboBox()
        self.reference.addItem("All overlapping images", ALL_OVERLAPPING)
        for item in project.inputs:
            if item.key != movingKey:
                self.reference.addItem(item.image.name, item.key)
        self.method = QComboBox()
        for method in MatchMethod:
            self.method.addItem(method.value, method)
        self.bandCount = QSpinBox()
        self.bandCount.setRange(1, max(1, moving.image.bandCount))
        self.bandCount.setValue(min(DEFAULT_BAND_COUNT, moving.image.bandCount))
        self.bandCount.setToolTip(
            "Match on this many bands with the best SNR, spread across the "
            "spectrum; their tie points are fitted together"
        )
        self.tileSize = QComboBox()
        for size in TILE_SIZES:
            self.tileSize.addItem(f"{size} px", size)
        self.tileSize.setCurrentIndex(TILE_SIZES.index(DEFAULT_TILE))
        self.refine = QCheckBox("Sub-pixel refinement (phase-plane fit)")
        self.refine.setChecked(True)
        self.refine.setToolTip(
            "Refine each match to about 1/50 pixel with the phase-plane fit of "
            "Leprince et al. (2007), the method behind COSI-Corr"
        )
        self.threshold = QDoubleSpinBox()
        self.threshold.setRange(0.05, 100.0)
        self.threshold.setSingleStep(0.25)
        self.threshold.setValue(DEFAULT_INLIER_PX)
        self.threshold.setSuffix(" px")
        self.threshold.setToolTip(
            "The fit leaves out automatic tie points farther off than this "
            "(RANSAC); manual points are always kept"
        )
        form = QFormLayout()
        form.addRow("Match against:", self.reference)
        form.addRow("Method:", self.method)
        if moving.image.bandCount > 1:
            form.addRow("Bands:", self.bandCount)
        form.addRow("Tile size:", self.tileSize)
        form.addRow("", self.refine)
        form.addRow("Outlier threshold:", self.threshold)
        model = moving.model.value.lower()
        guidance = MutedLabel(
            f"The tie points are fitted with the image's transform ({model}); "
            "choose it in the Images panel. For map-projected images a "
            "translation (or affine) is usually right; for unprojected strips "
            "whose distortion varies, a polynomial or thin-plate spline."
        )
        guidance.setWordWrap(True)

        self.runButton = QPushButton("Align")
        self.runButton.setDefault(True)
        self.runButton.clicked.connect(self._run)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setVisible(False)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.bands = QTableWidget(0, len(BAND_COLUMNS))
        self.bands.setHorizontalHeaderLabels(BAND_COLUMNS)
        vertical, header = self.bands.verticalHeader(), self.bands.horizontalHeader()
        assert vertical is not None and header is not None
        vertical.setVisible(False)
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.bands.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.bands.itemChanged.connect(self._onBandChanged)
        self.bands.setMinimumHeight(170)  # a header and five bands
        self.bands.setVisible(False)
        self.bandsNote = MutedLabel(
            "A band whose points disagree (an atmospheric band or a detector "
            "artifact, say) shows a high RMS or few kept points: untick it to "
            "fit without it."
        )
        self.bandsNote.setWordWrap(True)
        self.bandsNote.setVisible(False)
        self.fieldButton = QPushButton("Add Displacement Field to Images")
        self.fieldButton.setToolTip(
            "The tile shifts as an image (east and north displacement in map "
            "units, and match quality), as COSI-Corr produces"
        )
        self.fieldButton.clicked.connect(self._addFields)
        self.fieldButton.setVisible(False)
        close = QPushButton("Close")
        close.clicked.connect(self.close)

        buttons = QHBoxLayout()
        buttons.addWidget(self.runButton)
        buttons.addWidget(self.progress, 1)
        buttons.addStretch()
        buttons.addWidget(self.fieldButton)
        buttons.addWidget(close)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(guidance)
        layout.addWidget(self.summary)
        layout.addWidget(self.bands, 1)
        layout.addWidget(self.bandsNote)
        layout.addLayout(buttons)

    def settings(self) -> MatchSettings:
        return MatchSettings(
            bandCount=self.bandCount.value(),
            tileSize=int(self.tileSize.currentData()),
            refine=self.refine.isChecked(),
            method=self.method.currentData(),
        )

    def referenceKeys(self) -> list[int]:
        chosen = int(self.reference.currentData())
        if chosen != ALL_OVERLAPPING:
            return [chosen]
        return [i.key for i in self.project.inputs if i.key != self.movingKey]

    def _run(self) -> None:
        self.runButton.setEnabled(False)
        self.progress.setValue(0)
        self.progress.setVisible(True)
        self.summary.setText("Matching…")
        self.sigRun.emit(
            self.movingKey,
            self.referenceKeys(),
            self.settings(),
            self.threshold.value(),
        )

    def showProgress(self, fraction: float, message: str) -> None:
        self.progress.setValue(int(100 * fraction))
        self.summary.setText(message[:1].upper() + message[1:] + "…")

    def showFailure(self, message: str) -> None:
        self.runButton.setEnabled(True)
        self.progress.setVisible(False)
        self.summary.setText(message)

    def showResult(self, result: AutoAlignResult, fitMessage: str) -> None:
        """The matching's outcome and the fit's (``fitMessage``)."""
        self.alignment = result
        self.runButton.setEnabled(True)
        self.progress.setVisible(False)
        method = (
            "features" if result.method is MatchMethod.FEATURES else "phase correlation"
        )
        lines = [f"{result.added} tie points by {method}. {fitMessage}"]
        if result.message:
            lines.append(result.message)
        self.summary.setText(" ".join(lines))
        self.fieldButton.setVisible(bool(result.fields))
        self.showBands()

    def showBands(self) -> None:
        """Each band's points and how they agreed with the fit."""
        if self.alignment is None:
            return
        report = self.project.bandReport(self.movingKey)
        auto = [p for p in self.project.tiePointsOf(self.movingKey) if p.auto]
        centers = self.project.input(self.movingKey).image.bandModel.centers
        self.bands.blockSignals(True)
        self.bands.setRowCount(len(self.alignment.bands))
        for row, band in enumerate(self.alignment.bands):
            fit = report.get(band, BandFit(0, 0, float("nan")))
            used = any(p.band == band and p.enabled for p in auto) or not any(
                p.band == band for p in auto
            )
            cells = [
                str(band + 1),
                "" if centers is None else f"{centers[band]:.1f} nm",
                f"{self.alignment.snr[band]:.1f}",
                str(fit.count if used else sum(p.band == band for p in auto)),
                str(fit.inliers) if used else "",
                "" if not used or np.isnan(fit.rms) else f"{fit.rms:.3f}",
            ]
            for column, text in enumerate(cells):
                self.bands.setItem(row, column, QTableWidgetItem(text))
            use = QTableWidgetItem()
            use.setFlags(use.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            use.setCheckState(
                Qt.CheckState.Checked if used else Qt.CheckState.Unchecked
            )
            use.setData(Qt.ItemDataRole.UserRole, band)
            self.bands.setItem(row, len(BAND_COLUMNS) - 1, use)
        self.bands.blockSignals(False)
        multiple = len(self.alignment.bands) > 1
        if multiple and not self.bands.isVisible():
            self.bands.setVisible(True)
            self.bandsNote.setVisible(True)
            self.adjustSize()
        self.bands.setVisible(multiple)
        self.bandsNote.setVisible(multiple)

    def _onBandChanged(self, item: QTableWidgetItem) -> None:
        if item.column() == len(BAND_COLUMNS) - 1:
            band = int(item.data(Qt.ItemDataRole.UserRole))
            self.sigBandUsed.emit(
                self.movingKey, band, item.checkState() == Qt.CheckState.Checked
            )

    def _addFields(self) -> None:
        if self.alignment is not None:
            for displacement in self.alignment.fields:
                self.sigAddField.emit(displacement)
            self.fieldButton.setEnabled(False)
