"""Accuracy Assessment: a class map against ROI classes as ground truth, its
report (dialog, CSV) and what is kept with the result."""

import numpy as np
import pytest
from PyQt6.QtCore import Qt
from shapely.geometry import box

from varda.analysis.accuracy_assessment import (
    AccuracyAssessmentAnalysis,
    accuracyRecord,
    matchClasses,
    reportCsv,
)
from varda.accuracy_report_dialog import AccuracyReportDialog
from varda.analysis.analysis import AnalysisContext
from varda.analysis.class_tools import classRaster
from varda.analysis.provenance import recordProvenance
from varda.analysis.registry import ANALYSES
from varda.common.entities import Color, ROIMode, VardaRaster
from varda.common.layout_audit import assertNothingClipped
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.image_loading.raster_writer import writeRaster
from varda.image_loading.data_sources.rasterio_data_source import RasterioDataSource
from varda.rois.roi_collection import ROICollection

RED, BLUE, GRAY = Color(1, 0, 0, 0.5), Color(0, 0, 1, 0.5), Color(0.5, 0.5, 0.5, 0.5)


def _classMap() -> VardaRaster:
    """10 × 20: columns 0-9 class 0 ("Basalt"), 10-19 class 1 ("Dust"), except
    a 2 × 2 block of "Dust" at rows 0-1, columns 0-1; pixel (9, 19) unclassified."""
    image = VardaRaster(ArrayDataSource(np.zeros((10, 20, 1))), name="scene")
    classes = np.zeros((10, 20))
    classes[:, 10:] = 1
    classes[0:2, 0:2] = 1
    classes[9, 19] = np.nan
    return classRaster(
        image,
        classes,
        ["Basalt", "Dust"],
        ["#ff0000", "#0000ff"],
        name="scene classes",
        description="test map",
    )


def _rois() -> ROICollection:
    rois = ROICollection()
    rois.addROI(box(0, 0, 4, 4), "basalt ", RED, ROIMode.RECTANGLE)  # 16 px, 4 wrong
    rois.addROI(
        box(16, 6, 20, 10), "Dust", BLUE, ROIMode.RECTANGLE
    )  # 16, 1 unclassified
    rois.addROI(box(5, 5, 7, 7), "Ice", GRAY, ROIMode.RECTANGLE)  # no such map class
    return rois


def _run(rois=None):
    analysis = AccuracyAssessmentAnalysis()
    analysis.setContext(AnalysisContext(rois=rois or _rois()))
    classMap = _classMap()
    analysis.prepareFor(classMap)
    return analysis, classMap, analysis.run(classMap, lambda p, m: None)


def test_is_registered_under_classification():
    assert AccuracyAssessmentAnalysis in ANALYSES
    assert AccuracyAssessmentAnalysis.category == "Classification"
    assert AccuracyAssessmentAnalysis.needsRois


def test_matches_roi_classes_by_name_ignoring_case_and_spaces():
    matched, unmatched = matchClasses(["Basalt", "Dust"], ["basalt ", "Dust", "Ice"])
    assert matched == {"basalt ": 0, "Dust": 1}
    assert unmatched == ["Ice"]


def test_confusion_matrix_from_ground_truth_rois():
    _, _, result = _run()
    record = result.extraMetadata["accuracy"]
    report = record["report"]
    # rows = map, columns = reference
    assert report["matrix"] == [[12, 0], [4, 15]]
    assert report["totalPixels"] == 31
    assert report["overallAccuracy"] == pytest.approx(27 / 31)
    assert record["unmatchedRoiClasses"] == ["Ice"]
    assert record["unclassifiedReferencePixels"] == 1
    assert record["referenceRois"]["basalt "] == {
        "mapClass": "Basalt",
        "rois": 1,
        "pixels": 16,
    }
    assert any("Ice" in note for note in record["notes"])


def test_the_result_is_an_error_map():
    _, _, result = _run()
    assert result.bandNames == ["Class"]
    assert result.extraMetadata["classes"] == ["Correct", "Incorrect"]
    errors = result.getData()[:, :, 0]
    assert np.all(errors[0:2, 0:2] == 1)  # mapped Dust, truly basalt
    assert np.all(errors[2:4, 0:4] == 0)
    assert np.isnan(errors[9, 19])  # unclassified
    assert np.isnan(errors[5, 5])  # Ice: not a reference class
    assert np.isnan(errors[8, 8])  # outside every ROI
    assert "overall accuracy 87.1%" in result.dataSource.description


def test_unavailable_without_a_class_map_or_a_matching_class():
    analysis = AccuracyAssessmentAnalysis()
    analysis.setContext(AnalysisContext(rois=_rois()))
    plain = VardaRaster(ArrayDataSource(np.zeros((10, 20, 3))), name="plain")
    assert "class map" in analysis.unavailableReason(plain)
    analysis.prepareFor(_classMap())
    analysis.rois.set(["Ice"])
    assert "None of the ticked ROI classes" in analysis.unavailableReason(_classMap())
    analysis.rois.set(["Dust"])
    assert analysis.unavailableReason(_classMap()) == ""


def test_csv_names_the_class_map_its_provenance_and_the_reference(tmp_path):
    analysis, classMap, result = _run()
    recordProvenance(result, analysis, classMap)
    record = accuracyRecord(result)
    assert record is not None
    text = reportCsv(record, result)
    header = [line for line in text.splitlines() if line.startswith("#")]
    assert header[0].startswith("# Varda ") and "Accuracy assessment" in header[0]
    assert "# Class map: scene classes" in header
    assert "# Reference ROI class Dust: 1 ROIs, 15 pixels" in header
    assert "Map \\ Reference,Basalt,Dust,Total" in text


def test_the_report_is_in_the_provenance_and_survives_export(tmp_path):
    analysis, classMap, result = _run()
    recordProvenance(result, analysis, classMap)
    provenance = result.extraMetadata["provenance"]
    assert provenance["results"]["accuracy"]["report"]["matrix"] == [[12, 0], [4, 15]]

    path = writeRaster(result, tmp_path / "errors.tif")
    reread = VardaRaster(RasterioDataSource(str(path)), name="errors")
    assert reread.extraMetadata["accuracy"]["report"]["matrix"] == [[12, 0], [4, 15]]
    assert accuracyRecord(reread) is not None


def test_report_dialog_shows_the_tables_and_fits_a_laptop(qtbot):
    _, classMap, result = _run()
    dialog = AccuracyReportDialog([classMap, result], image=result)
    qtbot.addWidget(dialog)
    dialog.resize(560, 480)
    dialog.show()
    qtbot.waitExposed(dialog)

    assert "87.1%" in dialog.summaryLabel.text()
    matrix = dialog.matrixTable.model()
    assert matrix is not None
    assert matrix.data(matrix.index(1, 1), Qt.ItemDataRole.DisplayRole) == "4"
    perClass = dialog.classTable.model()
    assert perClass is not None
    assert perClass.data(perClass.index(0, 3), Qt.ItemDataRole.DisplayRole) == "75.0%"
    assert "Ice" in dialog.notesLabel.text()
    assert dialog.saveButton.isEnabled()
    assertNothingClipped(dialog)


def test_report_dialog_explains_an_image_without_a_report(qtbot):
    classMap = _classMap()
    dialog = AccuracyReportDialog([classMap], image=classMap)
    qtbot.addWidget(dialog)
    assert "no accuracy report" in dialog.summaryLabel.text()
    assert not dialog.saveButton.isEnabled()
