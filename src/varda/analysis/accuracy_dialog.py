"""Accuracy Report: the confusion matrix and accuracy measures an image
carries (an Accuracy Assessment result, or a classifier's hold-out
validation), shown as tables and saved as CSV."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QStandardItem, QStandardItemModel
from PyQt6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QLabel,
    QMessageBox,
    QTableView,
    QWidget,
)

from varda.analysis.accuracy import INTERVAL_METHOD, AccuracyReport
from varda.analysis.accuracy_assessment import accuracyRecord, reportCsv
from varda.common.entities import VardaRaster
from varda.common.parameter import ImageParameter
from varda.common.parameter_widgets import parameterWidget
from varda.common.ui import ButtonBuilder, HBoxBuilder, SectionBox, VBoxBuilder

_CLASS_COLUMNS = (
    "Class",
    "Reference px",
    "Map px",
    "Producer's",
    "Producer's 95%",
    "User's",
    "User's 95%",
    "Omission",
    "Commission",
)


def _percent(value: float | None) -> str:
    return "—" if value is None or math.isnan(value) else f"{100 * value:.1f}%"


def _interval(bounds: Sequence[float | None]) -> str:
    low, high = bounds
    if low is None or high is None:
        return "—"
    return f"{100 * low:.1f}–{100 * high:.1f}%"


def _model(header: Sequence[str], rows: Sequence[Sequence[str]]) -> QStandardItemModel:
    model = QStandardItemModel(len(rows), len(header))
    model.setHorizontalHeaderLabels(list(header))
    for r, row in enumerate(rows):
        for c, text in enumerate(row):
            item = QStandardItem(text)
            item.setEditable(False)
            if c:
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
            model.setItem(r, c, item)
    return model


def summaryText(record: Mapping) -> str:
    """One line: what was assessed and the headline numbers."""
    report = record["report"]
    kind = record.get("kind", "Accuracy")
    if not report["totalPixels"]:
        return f"{kind}: no reference pixels to assess."
    kappa = report["kappa"]
    return (
        f"<b>{kind}</b> on {report['totalPixels']} reference pixels: overall "
        f"accuracy <b>{_percent(report['overallAccuracy'])}</b> (95% interval "
        f"{_interval(report['overallInterval'])}), kappa "
        + ("—" if kappa is None else f"{kappa:.3f}")
        + "."
    )


class AccuracyReportDialog(QDialog):
    def __init__(
        self,
        images: Sequence[VardaRaster],
        *,
        image: VardaRaster | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Accuracy Report")
        self.resize(720, 560)
        self.setMinimumSize(420, 360)
        self.imageParam = ImageParameter(
            "Image", "An Accuracy Assessment result, or a classifier's result"
        )
        withReports = [i for i in images if accuracyRecord(i) is not None]
        if image is not None and image not in withReports:
            withReports.append(image)
        self.imageParam.setProvider(lambda: withReports)
        if image is not None:
            self.imageParam.set(image)

        self.summaryLabel = QLabel()
        self.summaryLabel.setWordWrap(True)
        self.matrixTable = QTableView()
        self.matrixTable.setMinimumHeight(100)
        self.classTable = QTableView()
        self.classTable.setMinimumHeight(100)
        self.notesLabel = QLabel()
        self.notesLabel.setWordWrap(True)
        self.saveButton = ButtonBuilder("Save CSV…").onClick(self._saveCsv)

        form = QFormLayout()
        form.addRow("Image", parameterWidget(self.imageParam))
        self.setLayout(
            VBoxBuilder()
            .withLayout(form)
            .withWidget(self.summaryLabel)
            .withWidget(
                SectionBox(
                    "Confusion matrix (rows: map class, columns: reference class)",
                    self.matrixTable,
                ),
                1,
            )
            .withWidget(SectionBox("Per class", self.classTable), 1)
            .withWidget(self.notesLabel)
            .withLayout(
                HBoxBuilder()
                .withWidget(self.saveButton)
                .withStretch()
                .withWidget(ButtonBuilder("Close").onClick(self.close))
            )
        )
        self.imageParam.sigParameterChanged.connect(lambda _: self._showImage())
        self._showImage()

    def selectedImage(self) -> VardaRaster | None:
        return self.imageParam.get()

    def _showImage(self) -> None:
        image = self.selectedImage()
        record = accuracyRecord(image) if image is not None else None
        self.saveButton.setEnabled(record is not None)
        if record is None:
            self.summaryLabel.setText(
                "This image has no accuracy report. Run Accuracy Assessment "
                "(Processing → Classification), or a classifier with Hold Out "
                "above 0, and pick its result here."
            )
            self.matrixTable.setModel(None)
            self.classTable.setModel(None)
            self.notesLabel.setText("")
            return
        report = AccuracyReport.fromDict(record["report"])
        self.summaryLabel.setText(summaryText(record))
        self.matrixTable.setModel(
            _model(
                ["Map \\ Reference", *report.classes, "Total"],
                [
                    [name, *map(str, report.matrix[k]), str(report.mapTotals[k])]
                    for k, name in enumerate(report.classes)
                ]
                + [
                    [
                        "Total",
                        *map(str, report.referenceTotals),
                        str(report.total),
                    ]
                ],
            )
        )
        self.classTable.setModel(
            _model(
                _CLASS_COLUMNS,
                [
                    [
                        entry["class"],
                        str(entry["referencePixels"]),
                        str(entry["mapPixels"]),
                        _percent(entry["producersAccuracy"]),
                        _interval(entry["producersInterval"]),
                        _percent(entry["usersAccuracy"]),
                        _interval(entry["usersInterval"]),
                        _percent(entry["omissionError"]),
                        _percent(entry["commissionError"]),
                    ]
                    for entry in report.perClass()
                ],
            )
        )
        for table in (self.matrixTable, self.classTable):
            table.resizeColumnsToContents()
        notes = [
            f"Intervals: {INTERVAL_METHOD}. They treat pixels as independent; "
            "pixels in one ROI are not, so the true uncertainty is larger.",
            *record.get("notes", []),
        ]
        self.notesLabel.setText("\n".join(notes))

    def _saveCsv(self) -> None:
        image = self.selectedImage()
        record = accuracyRecord(image) if image is not None else None
        if image is None or record is None:
            return
        folder = Path(image.filePath).parent if image.filePath else Path.home()
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save accuracy report",
            str(folder / f"{image.name} accuracy.csv"),
            "CSV (*.csv)",
        )
        if not path:
            return
        try:
            Path(path).write_text(reportCsv(record, image), encoding="utf-8")
        except OSError as error:
            QMessageBox.critical(
                self, "Save failed", f"Could not save {path}:\n{error}"
            )
