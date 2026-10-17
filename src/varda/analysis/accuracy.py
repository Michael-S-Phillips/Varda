"""Classification accuracy: the confusion (error) matrix and the measures
derived from it (Congalton 1991; Olofsson et al. 2014).

The matrix follows Congalton's layout: **rows are the map (classified)
class, columns the reference class**, entries are pixel counts. From it:

- overall accuracy  OA = Σ nᵢᵢ / N, with a 95% Wilson score interval
  (Wilson 1927), which assumes independent pixels;
- Cohen's kappa  κ = (p_o − p_e) / (1 − p_e), p_o = OA,
  p_e = Σ nᵢ₊ n₊ᵢ / N²  (Cohen 1960);
- producer's accuracy of class j = n_jj / n₊ⱼ (of the reference pixels of
  j, the share mapped as j; 1 − it is the omission error), and user's
  accuracy of class i = nᵢᵢ / nᵢ₊ (of the pixels mapped as i, the share that
  are i; 1 − it is the commission error), each with a Wilson interval.

A measure with nothing to divide by (a class with no reference or no mapped
pixels) is NaN, and ``None`` in ``toDict``. Qt-free.
"""

from __future__ import annotations

import csv
import io
import math
from collections.abc import Mapping, Sequence

import attrs
import numpy as np

# Two-sided 95%: the 0.975 quantile of the standard normal distribution
Z_95 = 1.959963984540054
INTERVAL_METHOD = "Wilson score interval, 95% (Wilson 1927)"
LAYOUT = "rows = map (classified) class, columns = reference class; pixel counts"


def wilsonInterval(successes: int, trials: int, z: float = Z_95) -> tuple[float, float]:
    """The Wilson score interval for a proportion ``successes / trials``
    ((NaN, NaN) when ``trials`` is 0)."""
    if trials <= 0:
        return math.nan, math.nan
    p = successes / trials
    scale = 1 + z**2 / trials
    center = (p + z**2 / (2 * trials)) / scale
    half = z / scale * math.sqrt(p * (1 - p) / trials + z**2 / (4 * trials**2))
    return max(0.0, center - half), min(1.0, center + half)


def confusionMatrix(
    reference: np.ndarray, predicted: np.ndarray, classCount: int
) -> np.ndarray:
    """(classCount, classCount) pixel counts, rows = predicted (map) class,
    columns = reference class. Both inputs are 0-based class numbers of the
    same pixels."""
    reference = np.asarray(reference, dtype=np.int64).ravel()
    predicted = np.asarray(predicted, dtype=np.int64).ravel()
    if reference.shape != predicted.shape:
        raise ValueError("Reference and predicted labels must be the same length.")
    inRange = (
        (reference >= 0)
        & (reference < classCount)
        & (predicted >= 0)
        & (predicted < classCount)
    )
    if not inRange.all():
        raise ValueError("Class numbers must be between 0 and the class count - 1.")
    flat = np.bincount(
        predicted * classCount + reference, minlength=classCount * classCount
    )
    return flat.reshape(classCount, classCount)


def _ratio(numerator: np.ndarray, denominator: np.ndarray) -> np.ndarray:
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(denominator > 0, numerator / denominator, np.nan)


def _orNone(value: float) -> float | None:
    return None if math.isnan(value) else float(value)


@attrs.frozen(eq=False)
class AccuracyReport:
    """A confusion matrix and the measures derived from it."""

    classes: tuple[str, ...]
    matrix: np.ndarray = attrs.field(converter=lambda m: np.asarray(m, np.int64))

    @property
    def total(self) -> int:
        return int(self.matrix.sum())

    @property
    def correct(self) -> int:
        return int(np.trace(self.matrix))

    @property
    def referenceTotals(self) -> np.ndarray:
        """Reference pixels of each class (column sums)."""
        return self.matrix.sum(axis=0)

    @property
    def mapTotals(self) -> np.ndarray:
        """Pixels mapped as each class (row sums)."""
        return self.matrix.sum(axis=1)

    @property
    def overallAccuracy(self) -> float:
        return self.correct / self.total if self.total else math.nan

    @property
    def overallInterval(self) -> tuple[float, float]:
        return wilsonInterval(self.correct, self.total)

    @property
    def kappa(self) -> float:
        if not self.total:
            return math.nan
        expected = float(self.mapTotals @ self.referenceTotals) / self.total**2
        if expected >= 1:
            return math.nan
        return (self.overallAccuracy - expected) / (1 - expected)

    @property
    def producersAccuracy(self) -> np.ndarray:
        return _ratio(np.diag(self.matrix), self.referenceTotals)

    @property
    def usersAccuracy(self) -> np.ndarray:
        return _ratio(np.diag(self.matrix), self.mapTotals)

    @property
    def omissionError(self) -> np.ndarray:
        return 1 - self.producersAccuracy

    @property
    def commissionError(self) -> np.ndarray:
        return 1 - self.usersAccuracy

    def producersInterval(self, k: int) -> tuple[float, float]:
        return wilsonInterval(int(self.matrix[k, k]), int(self.referenceTotals[k]))

    def usersInterval(self, k: int) -> tuple[float, float]:
        return wilsonInterval(int(self.matrix[k, k]), int(self.mapTotals[k]))

    def perClass(self) -> list[dict]:
        """One entry per class: counts, accuracies and their intervals."""
        rows = []
        for k, name in enumerate(self.classes):
            pLow, pHigh = self.producersInterval(k)
            uLow, uHigh = self.usersInterval(k)
            rows.append(
                {
                    "class": name,
                    "referencePixels": int(self.referenceTotals[k]),
                    "mapPixels": int(self.mapTotals[k]),
                    "correctPixels": int(self.matrix[k, k]),
                    "producersAccuracy": _orNone(self.producersAccuracy[k]),
                    "producersInterval": [_orNone(pLow), _orNone(pHigh)],
                    "usersAccuracy": _orNone(self.usersAccuracy[k]),
                    "usersInterval": [_orNone(uLow), _orNone(uHigh)],
                    "omissionError": _orNone(self.omissionError[k]),
                    "commissionError": _orNone(self.commissionError[k]),
                }
            )
        return rows

    def toDict(self) -> dict:
        """JSON-friendly: the matrix and every measure (for metadata,
        provenance and files)."""
        low, high = self.overallInterval
        return {
            "classes": list(self.classes),
            "matrix": self.matrix.tolist(),
            "layout": LAYOUT,
            "totalPixels": self.total,
            "correctPixels": self.correct,
            "overallAccuracy": _orNone(self.overallAccuracy),
            "overallInterval": [_orNone(low), _orNone(high)],
            "intervalMethod": INTERVAL_METHOD,
            "kappa": _orNone(self.kappa),
            "perClass": self.perClass(),
        }

    @classmethod
    def fromDict(cls, data: Mapping) -> AccuracyReport:
        return cls(tuple(data["classes"]), np.asarray(data["matrix"]))

    def csvText(self, header: Sequence[str] = ()) -> str:
        """The matrix, the per-class measures and the summary as CSV, after
        ``header`` lines written as ``#`` comments."""
        out = io.StringIO()
        for line in header:
            out.write(f"# {line}\n")
        out.write(f"# Confusion matrix: {LAYOUT}\n")
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(["Map \\ Reference", *self.classes, "Total"])
        for k, name in enumerate(self.classes):
            writer.writerow([name, *self.matrix[k].tolist(), int(self.mapTotals[k])])
        writer.writerow(["Total", *self.referenceTotals.tolist(), self.total])
        writer.writerow([])
        writer.writerow(
            [
                "Class",
                "Reference pixels",
                "Map pixels",
                "Correct pixels",
                "Producer's accuracy",
                "Producer's 95% low",
                "Producer's 95% high",
                "User's accuracy",
                "User's 95% low",
                "User's 95% high",
                "Omission error",
                "Commission error",
            ]
        )
        for entry in self.perClass():
            writer.writerow(
                [
                    entry["class"],
                    entry["referencePixels"],
                    entry["mapPixels"],
                    entry["correctPixels"],
                    _cell(entry["producersAccuracy"]),
                    *map(_cell, entry["producersInterval"]),
                    _cell(entry["usersAccuracy"]),
                    *map(_cell, entry["usersInterval"]),
                    _cell(entry["omissionError"]),
                    _cell(entry["commissionError"]),
                ]
            )
        writer.writerow([])
        low, high = self.overallInterval
        writer.writerow(["Measure", "Value"])
        writer.writerow(["Total pixels", self.total])
        writer.writerow(["Correct pixels", self.correct])
        writer.writerow(["Overall accuracy", _cell(self.overallAccuracy)])
        writer.writerow(["Overall accuracy 95% low", _cell(low)])
        writer.writerow(["Overall accuracy 95% high", _cell(high)])
        writer.writerow(["Interval method", INTERVAL_METHOD])
        writer.writerow(["Kappa", _cell(self.kappa)])
        return out.getvalue()


def _cell(value: float | None) -> str:
    return "" if value is None or math.isnan(value) else f"{value:.6g}"


def assessAccuracy(
    reference: np.ndarray, predicted: np.ndarray, classes: Sequence[str]
) -> AccuracyReport:
    """The accuracy of ``predicted`` against ``reference`` (0-based class
    numbers into ``classes``, one entry per reference pixel)."""
    return AccuracyReport(
        tuple(classes), confusionMatrix(reference, predicted, len(classes))
    )
