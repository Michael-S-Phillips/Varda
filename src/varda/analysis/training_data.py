"""Training (and hold-out validation) pixels from a workspace's ROI classes.

Shared by every supervised classifier:

- **Ambiguous pixels** -- inside ROIs of two or more of the chosen classes --
  are left out of training and validation, and counted.
- **Hold-out validation** sets aside whole ROIs, not random pixels: from a
  class with n ROIs, round(fraction × n) of them (at least 1, at most n − 1),
  picked at random with the classifier's seed. A class with one ROI can't be
  split; it is used for training only, and a note says so.
- A pixel inside both a training and a held-out ROI of the same class trains
  (it is left out of validation).

Qt-free.
"""

from __future__ import annotations

from collections.abc import Sequence

import attrs
import numpy as np

from varda.analysis.accuracy import AccuracyReport, assessAccuracy
from varda.common.entities import VardaRaster
from varda.rois.roi_collection import ROICollection


def heldOutCount(rois: int, fraction: float) -> int:
    """How many of a class's ``rois`` to hold out for validation."""
    if fraction <= 0 or rois < 2:
        return 0
    return int(min(rois - 1, max(1, np.floor(fraction * rois + 0.5))))


@attrs.frozen(eq=False)
class TrainingData:
    """The chosen classes' training and validation pixels (row, column and
    0-based class number), and what to record about them."""

    names: list[str]
    rows: np.ndarray
    cols: np.ndarray
    labels: np.ndarray
    validationRows: np.ndarray
    validationCols: np.ndarray
    validationLabels: np.ndarray
    record: dict  # the result's "trainingData" metadata
    notes: list[str]

    @property
    def hasValidation(self) -> bool:
        return self.validationLabels.size > 0

    def validate(self, classMap: np.ndarray) -> AccuracyReport:
        """The accuracy of ``classMap`` (0-based class numbers over the
        image) on the held-out pixels."""
        predicted = classMap[self.validationRows, self.validationCols]
        return assessAccuracy(self.validationLabels, predicted, self.names)

    def validationRecord(self, classMap: np.ndarray) -> dict:
        """The result's "validation" metadata: the hold-out accuracy and the
        ROIs and pixels it rests on."""
        return {
            "kind": "Hold-out validation",
            "report": self.validate(classMap).toDict(),
            "referenceRois": {
                entry["name"]: {
                    "rois": entry["validationRois"],
                    "pixels": entry["validationPixels"],
                }
                for entry in self.record["classes"]
            },
            "ambiguousPixels": self.record["ambiguousPixels"],
            "notes": list(self.notes),
        }


def collectTrainingData(
    rois: ROICollection,
    image: VardaRaster,
    valid: np.ndarray,
    classes: Sequence[str],
    *,
    holdOut: float = 0.0,
    seed: int = 0,
) -> TrainingData:
    """Training and validation pixels of ``classes`` (valid pixels only)."""
    if len(classes) < 2:
        raise ValueError("Training needs at least two ROI classes.")
    groups = rois.classes()
    rng = np.random.default_rng(seed)
    covering = np.zeros(valid.shape, dtype=np.uint16)  # classes over each pixel
    training = np.full(valid.shape, -1, dtype=np.int32)
    held = np.full(valid.shape, -1, dtype=np.int32)
    entries, notes = [], []
    for k, name in enumerate(classes):
        fids = groups.get(name, [])
        count = heldOutCount(len(fids), holdOut)
        if holdOut > 0 and len(fids) < 2:
            notes.append(
                f"“{name}” has only one ROI, so none could be held out: it is "
                "used for training only and is not validated."
            )
        heldNumbers = sorted(int(i) for i in rng.permutation(len(fids))[:count])
        trainMask = np.zeros(valid.shape, dtype=bool)
        heldMask = np.zeros(valid.shape, dtype=bool)
        for i, fid in enumerate(fids):
            mask = rois.getMask(fid, image) & valid
            if i in heldNumbers:
                heldMask |= mask
            else:
                trainMask |= mask
        heldMask &= ~trainMask
        covering += trainMask | heldMask
        training[trainMask] = k
        held[heldMask] = k
        entries.append(
            {
                "name": name,
                "rois": len(fids),
                "trainingRois": len(fids) - count,
                "validationRois": count,
                "heldOutRoiNumbers": [i + 1 for i in heldNumbers],
            }
        )
    ambiguous = covering > 1
    training[ambiguous] = -1
    held[ambiguous] = -1
    ambiguousCount = int(ambiguous.sum())
    if ambiguousCount:
        notes.append(
            f"{ambiguousCount} pixels lie inside ROIs of two or more classes; "
            "they were left out of training and validation."
        )

    def pixels(labels: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        found = [np.nonzero(labels == k) for k in range(len(classes))]
        rows = np.concatenate([r for r, _ in found])
        cols = np.concatenate([c for _, c in found])
        numbers = np.concatenate(
            [np.full(r.size, k, dtype=np.int64) for k, (r, _) in enumerate(found)]
        )
        return rows, cols, numbers

    rows, cols, labels = pixels(training)
    vRows, vCols, vLabels = pixels(held)
    for k, entry in enumerate(entries):
        entry["trainingPixels"] = int((labels == k).sum())
        entry["validationPixels"] = int((vLabels == k).sum())
    if len(np.unique(labels)) < 2:
        raise ValueError("At least two ROI classes must contain valid pixels.")
    return TrainingData(
        names=list(classes),
        rows=rows,
        cols=cols,
        labels=labels,
        validationRows=vRows,
        validationCols=vCols,
        validationLabels=vLabels,
        record={
            "holdOutFraction": float(holdOut),
            "seed": int(seed),
            "ambiguousPixels": ambiguousCount,
            "classes": entries,
        },
        notes=notes,
    )
