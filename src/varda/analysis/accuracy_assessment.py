"""Accuracy Assessment: a class map against ROI classes as ground truth
(ENVI's "Confusion Matrix Using Ground Truth ROIs").

ROI classes are matched to the map's classes by name (ignoring case and
surrounding spaces). Reference pixels are the valid pixels inside the matched
classes' ROIs; a pixel inside ROIs of two or more of them is ambiguous and
left out. The result is an error map -- a class map of "Correct" and
"Incorrect" over the reference pixels, no data elsewhere -- whose metadata
(``"accuracy"``) holds the confusion matrix and its measures. Qt-free.
"""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from varda.analysis.accuracy import AccuracyReport, assessAccuracy
from varda.analysis.analysis import ProgressCallback
from varda.analysis.bandwise import readBand
from varda.analysis.class_tools import classRaster, isClassMap
from varda.analysis.classification import (
    _requireRois,
    _roiChoiceParameter,
    _RoiTrainingAnalysis,
)
from varda.common.entities import VardaRaster
from varda.common.provenance import provenanceText
from varda.version import vardaVersion

# Metadata keys holding an accuracy record: Accuracy Assessment's, and a
# classifier's hold-out validation
ACCURACY_KEYS = ("accuracy", "validation")
ERROR_CLASSES = ["Correct", "Incorrect"]
ERROR_COLORS = ["#1a9850", "#d73027"]


def _key(name: str) -> str:
    return name.strip().casefold()


def matchClasses(
    mapClasses: list[str], roiClasses: list[str]
) -> tuple[dict[str, int], list[str]]:
    """ROI class -> the map class number it matches (by name, ignoring case
    and surrounding spaces), and the ROI classes that match none."""
    numbers: dict[str, int] = {}
    for k, name in enumerate(mapClasses):
        numbers.setdefault(_key(name), k)
    matched = {
        name: numbers[_key(name)] for name in roiClasses if _key(name) in numbers
    }
    return matched, [name for name in roiClasses if name not in matched]


def accuracyRecord(image: VardaRaster) -> dict | None:
    """The accuracy record an image carries (an Accuracy Assessment result,
    or a classifier's hold-out validation), or None."""
    for key in ACCURACY_KEYS:
        record = image.extraMetadata.get(key)
        if isinstance(record, Mapping) and "report" in record:
            return dict(record)
    return None


def reportHeader(record: Mapping, holder: VardaRaster) -> list[str]:
    """The comment lines above a report's CSV: what was assessed, against
    which reference ROIs, with which Varda."""
    lines = [f"Varda {vardaVersion()} {record.get('kind', 'accuracy report')}"]
    classMap = record.get("classMap") or holder.name
    path = record.get("classMapPath") or ""
    lines.append(f"Class map: {classMap}" + (f" ({path})" if path else ""))
    made = record.get("classMapProvenance") or provenanceText(holder)
    if made:
        lines.append(f"Class map provenance: {made}")
    if holder.name != classMap:
        lines.append(f"Report kept with: {holder.name}")
    for name, entry in record.get("referenceRois", {}).items():
        lines.append(
            f"Reference ROI class {name}: {entry['rois']} ROIs, "
            f"{entry['pixels']} pixels"
        )
    lines += [f"Note: {note}" for note in record.get("notes", [])]
    return lines


def reportCsv(record: Mapping, holder: VardaRaster) -> str:
    """The record's report as CSV, with its header."""
    report = AccuracyReport.fromDict(record["report"])
    return report.csvText(reportHeader(record, holder))


class AccuracyAssessmentAnalysis(_RoiTrainingAnalysis):
    analysisId = "accuracy_assessment"
    name = "Accuracy Assessment"
    description = (
        "Compares a class map with ROI classes drawn as ground truth (matched "
        "by name): confusion matrix, overall accuracy with its 95% interval, "
        "kappa, and each class's producer's and user's accuracy. The result "
        "is an error map (Correct / Incorrect over the reference pixels)."
    )

    rois = _roiChoiceParameter(
        "The ROI classes to use as ground truth, matched to the class map's "
        "classes by name (ignoring case); all of them by default."
    )

    def unavailableReason(self, image: VardaRaster) -> str:
        if not isClassMap(image):
            return (
                "Choose a class map: the result of a classification or a density slice."
            )
        collection = self.context.rois
        if collection is None or len(collection) == 0:
            return ""  # the dialog already explains missing ROIs
        chosen = self._chosenClasses(collection)
        if not chosen:
            return "Tick at least one ROI class."
        matched, _ = matchClasses(list(image.extraMetadata["classes"]), chosen)
        if not matched:
            return (
                "None of the ticked ROI classes has the name of one of the "
                f"class map's classes ({', '.join(image.extraMetadata['classes'])})."
            )
        return ""

    def run(self, image: VardaRaster, reportProgress: ProgressCallback) -> VardaRaster:
        rois = _requireRois(self)
        if not isClassMap(image):
            raise ValueError("Accuracy Assessment needs a class map.")
        mapClasses = [str(name) for name in image.extraMetadata["classes"]]
        matched, unmatched = matchClasses(mapClasses, self._chosenClasses(rois))
        if not matched:
            raise ValueError("No ROI class matches a class of the class map by name.")

        reportProgress(0, "reading classes")
        predictedBand = readBand(image, 0)
        reportProgress(20, "collecting reference pixels")
        covering = np.zeros(predictedBand.shape, dtype=np.uint16)
        reference = np.full(predictedBand.shape, -1, dtype=np.int64)
        groups = rois.classes()
        for name, k in matched.items():
            mask = rois.classMask(name, image)
            covering += mask
            reference[mask] = k
        ambiguous = covering > 1
        reference[ambiguous] = -1
        isReference = reference >= 0
        classified = (
            np.isfinite(predictedBand)
            & (predictedBand >= 0)
            & (predictedBand < len(mapClasses))
        )
        unclassified = isReference & ~classified
        used = isReference & classified

        reportProgress(60, "computing the confusion matrix")
        predicted = predictedBand[used].astype(np.int64)
        report = assessAccuracy(reference[used], predicted, mapClasses)
        notes = []
        if unmatched:
            notes.append(
                "ROI classes that match no class of the map, left out: "
                + ", ".join(unmatched)
            )
        if ambiguous.any():
            notes.append(
                f"{int(ambiguous.sum())} pixels lie inside ROIs of two or more "
                "reference classes; they were left out."
            )
        if unclassified.any():
            notes.append(
                f"{int(unclassified.sum())} reference pixels are unclassified "
                "(no data) in the class map; they were left out."
            )
        withoutReference = [
            name for k, name in enumerate(mapClasses) if k not in matched.values()
        ]
        if withoutReference:
            notes.append(
                "Map classes without reference ROIs (no producer's accuracy): "
                + ", ".join(withoutReference)
            )
        record = {
            "kind": "Accuracy assessment",
            "classMap": image.name,
            "classMapPath": image.filePath or "",
            "classMapProvenance": provenanceText(image),
            "report": report.toDict(),
            "referenceRois": {
                name: {
                    "mapClass": mapClasses[k],
                    "rois": len(groups.get(name, [])),
                    "pixels": int(((reference == k) & used).sum()),
                }
                for name, k in matched.items()
            },
            "unmatchedRoiClasses": unmatched,
            "ambiguousPixels": int(ambiguous.sum()),
            "unclassifiedReferencePixels": int(unclassified.sum()),
            "notes": notes,
        }

        errors = np.full(predictedBand.shape, np.nan, dtype=np.float32)
        errors[used] = (predictedBand[used] != reference[used]).astype(np.float32)
        accuracy = report.overallAccuracy
        result = classRaster(
            image,
            errors,
            ERROR_CLASSES,
            ERROR_COLORS,
            name=f"{image.name} accuracy",
            description=(
                f"Accuracy assessment of {image.name} against "
                f"{len(matched)} ROI classes: overall accuracy "
                f"{100 * accuracy:.1f}% of {report.total} pixels"
                if report.total
                else f"Accuracy assessment of {image.name}: no reference pixels"
            ),
        )
        result.dataSource.extraMetadata["accuracy"] = record
        return result
