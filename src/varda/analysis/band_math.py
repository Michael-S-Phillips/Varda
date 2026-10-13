"""Band math: a new image from an expression over an image's bands.

    R2300 / R2200                  bands nearest 2300 and 2200 nm
    (b10 - b4) / (b10 + b4)        band numbers, 1-based (like ENVI's b1)
    where(b3 > 0.2, R2300, 0)      comparisons and where()

The expression is checked (syntax, functions, every band reference) before any
data is read, then evaluated in row chunks that read only the bands it uses.
A pixel with no data in any band the expression uses, and any non-finite
result, becomes NaN (so where() can't turn missing data into a value). The grammar is the
safe evaluator in ``common/expressions`` -- never ``eval``.
"""

from __future__ import annotations

import ast
import re

import numpy as np
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from varda.analysis.analysis import Analysis, ProgressCallback
from varda.analysis.rasters import singleBandRaster
from varda.common.entities import VardaRaster
from varda.common.expressions import ExpressionError as ExpressionError, evaluate, parse
from varda.common.parameter import StringParameter

CHUNK_ROWS = 256
BAND_FUNCTIONS = {
    "sqrt": np.sqrt,
    "log": np.log,
    "log10": np.log10,
    "exp": np.exp,
    "abs": np.abs,
    "min": np.minimum,
    "max": np.maximum,
    "where": np.where,
    "clip": np.clip,
}
CONSTANTS = {"pi": float(np.pi), "e": float(np.e)}
_REFERENCE = re.compile(r"^(?:R(?P<nm>\d+)|b(?P<band>\d+))$")
SETTINGS_KEY = "bandMath/saved"
MAX_SAVED = 20
HELP_TEXT = (
    "<b>R2300</b>: band nearest 2300 nm · <b>b12</b>: band 12 · "
    "+ − × / ** · comparisons (&lt; &gt; &lt;= &gt;= == !=) · "
    "functions: " + ", ".join(BAND_FUNCTIONS) + " · constants: pi, e"
)


def _referenceTolerance(centers: np.ndarray) -> float:
    spacing = (
        float(np.median(np.abs(np.diff(np.sort(centers))))) if centers.size > 1 else 0.0
    )
    return max(3.0 * spacing, 25.0)


def checkExpression(
    text: str, image: VardaRaster
) -> tuple[ast.Expression, dict[str, int]]:
    """The parsed expression and its band references (name -> band index);
    raises ExpressionError naming the problem. Reads no data."""
    tree = parse(
        text,
        lambda name: _REFERENCE.match(name) is not None,
        BAND_FUNCTIONS,
        CONSTANTS,
        comparisons=True,
        unknownName="unknown name '{}' (use R<nm> or b<band number>)",
    )
    model = image.bandModel
    references: dict[str, int] = {}
    for node in ast.walk(tree):
        if (
            not isinstance(node, ast.Name)
            or node.id in BAND_FUNCTIONS
            or node.id in CONSTANTS
        ):
            continue
        match = _REFERENCE.match(node.id)
        assert match is not None
        if match["band"] is not None:
            band = int(match["band"])
            if not 1 <= band <= image.bandCount:
                raise ExpressionError(
                    f"{node.id}: {image.name} has bands 1-{image.bandCount}"
                )
            references[node.id] = band - 1
            continue
        if model.centers is None:
            raise ExpressionError(
                f"{node.id}: {image.name} has no wavelengths; use band numbers (b1, b2...)"
            )
        target = float(match["nm"])
        good = np.flatnonzero(~model.badBands)
        index = int(good[np.argmin(np.abs(model.centers[good] - target))])
        if abs(model.centers[index] - target) > _referenceTolerance(
            model.centers[good]
        ):
            raise ExpressionError(
                f"{node.id}: no band near {target:g} nm "
                f"({image.name} covers {np.nanmin(model.centers):g}-{np.nanmax(model.centers):g} nm)"
            )
        references[node.id] = index
    return tree, references


def evaluateExpression(
    text: str, image: VardaRaster, progress: ProgressCallback | None = None
) -> np.ndarray:
    """The (rows, cols) float32 result of ``text`` on ``image``."""
    tree, references = checkExpression(text, image)
    bands = sorted(set(references.values()))
    position = {band: i for i, band in enumerate(bands)}
    noData = image.bandModel.noData
    out = np.empty((image.height, image.width), dtype=np.float32)
    for start in range(0, image.height, CHUNK_ROWS):
        rows = min(CHUNK_ROWS, image.height - start)
        values: dict[str, np.ndarray] = {}
        missing = np.zeros((rows, image.width), dtype=bool)
        if bands:
            chunk = np.asarray(
                image.getData(bandIndices=bands, window=(start, 0, rows, image.width)),
                dtype=np.float64,
            )
            if noData is not None:
                chunk[chunk == noData] = np.nan
            values = {name: chunk[:, :, position[b]] for name, b in references.items()}
            missing = np.isnan(chunk).any(axis=2)  # no data in a band it uses
        with np.errstate(all="ignore"):
            result = np.asarray(
                evaluate(tree, values, BAND_FUNCTIONS, CONSTANTS), dtype=np.float64
            )
        result = np.broadcast_to(result, (rows, image.width)).copy()
        result[~np.isfinite(result) | missing] = np.nan
        out[start : start + rows] = result
        if progress is not None:
            progress(
                int(100 * (start + rows) / image.height),
                f"rows {start + rows}/{image.height}",
            )
    return out


def _outputSize(image: VardaRaster) -> str:
    size = image.height * image.width * 4  # float32
    for unit in ("bytes", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.3g} {unit}" if unit != "bytes" else f"{size} bytes"
        size /= 1024
    return ""


class BandMathAnalysis(Analysis):
    analysisId = "band_math"
    name = "Band Math"
    category = "Spectral Parameters"
    description = (
        "A new image from an expression over the bands, e.g. R2300 / R2200 "
        "(bands nearest 2300 and 2200 nm) or (b10 - b4) / (b10 + b4)."
    )

    expression = StringParameter(
        "Expression",
        "R2300 / R2200",
        description="R<nm>, b<band>, + - * / **, where(...)",
    )

    def unavailableReason(self, image: VardaRaster) -> str:
        try:
            checkExpression(self.expression.get(), image)
        except ExpressionError as error:
            return str(error).capitalize()
        return ""

    def createPreviewWidget(self, image: VardaRaster) -> QWidget | None:
        return BandMathHelp(self, image)

    def run(self, image: VardaRaster, reportProgress: ProgressCallback) -> VardaRaster:
        text = self.expression.get().strip()
        reportProgress(0, "evaluating")
        values = evaluateExpression(text, image, reportProgress)
        return singleBandRaster(
            image, values, name=f"{image.name} [{text}]", bandName=text, units=""
        )


class BandMathHelp(QWidget):
    """What the references resolve to, the output size, the syntax, and saved
    expressions to reuse."""

    def __init__(
        self,
        analysis: BandMathAnalysis,
        image: VardaRaster,
        settings: QSettings | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.analysis = analysis
        self.image = image
        self.settings = settings if settings is not None else QSettings()
        self.referencesLabel = QLabel()
        self.referencesLabel.setWordWrap(True)
        helpLabel = QLabel(HELP_TEXT)
        helpLabel.setWordWrap(True)
        self.savedBox = QComboBox()
        self.savedBox.setPlaceholderText("Saved expressions")
        self.saveButton = QPushButton("Save Expression")
        saved = QHBoxLayout()
        saved.addWidget(self.savedBox, 1)
        saved.addWidget(self.saveButton)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.referencesLabel)
        layout.addWidget(
            QLabel(
                f"Result: {image.width} × {image.height} pixels, {_outputSize(image)}"
            )
        )
        layout.addWidget(helpLabel)
        layout.addLayout(saved)

        self._fillSaved()
        self.savedBox.textActivated.connect(self.analysis.expression.set)
        self.savedBox.currentTextChanged.connect(
            lambda text: text and self.analysis.expression.set(text)
        )
        self.saveButton.clicked.connect(self._save)
        self.analysis.expression.sigParameterChanged.connect(
            lambda _: self._showReferences()
        )
        self._showReferences()

    def _saved(self) -> list[str]:
        value = self.settings.value(SETTINGS_KEY, [])
        return [value] if isinstance(value, str) else list(value or [])

    def _fillSaved(self) -> None:
        self.savedBox.blockSignals(True)
        self.savedBox.clear()
        self.savedBox.addItems(self._saved())
        self.savedBox.setCurrentIndex(-1)
        self.savedBox.blockSignals(False)

    def _save(self) -> None:
        text = self.analysis.expression.get().strip()
        if not text:
            return
        entries = [text, *[e for e in self._saved() if e != text]][:MAX_SAVED]
        self.settings.setValue(SETTINGS_KEY, entries)
        self._fillSaved()

    def _showReferences(self) -> None:
        try:
            _, references = checkExpression(self.analysis.expression.get(), self.image)
        except ExpressionError as error:
            self.referencesLabel.setText(
                f"<span style='color:#d33'>{str(error).capitalize()}</span>"
            )
            return
        model = self.image.bandModel
        parts = []
        for name, band in references.items():
            where = ""
            if model.centers is not None:
                where = f" ({model.native([model.centers[band]])[0]:g} {model.label})"
            parts.append(f"{name} → band {band + 1}{where}")
        self.referencesLabel.setText(" · ".join(parts) or "No band references.")
