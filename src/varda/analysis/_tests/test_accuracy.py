"""The confusion matrix and accuracy measures, against a hand-worked example.

Map (rows) by reference (columns), 30 pixels:

            ref A  ref B  ref C | map total
    map A     8      1      1   |   10
    map B     2      6      0   |    8
    map C     0      3      9   |   12
    -------------------------------
    ref total 10     10     10  |   30

Overall accuracy 23/30. Chance agreement p_e = (10·10 + 8·10 + 12·10)/30² =
1/3, so kappa = (23/30 − 1/3)/(1 − 1/3) = 13/20. Producer's: 8/10, 6/10,
9/10; user's: 8/10, 6/8, 9/12. Wilson 95% for 23/30: z² = 3.8415,
center = (23/30 + z²/60)/(1 + z²/30) = 0.73640, half-width = 0.14568,
so (0.5907, 0.8821).
"""

import math

import numpy as np
import pytest

from varda.analysis.accuracy import (
    AccuracyReport,
    assessAccuracy,
    confusionMatrix,
    wilsonInterval,
)

MATRIX = [[8, 1, 1], [2, 6, 0], [0, 3, 9]]


def _labels() -> tuple[np.ndarray, np.ndarray]:
    """Reference and predicted labels that give MATRIX."""
    reference, predicted = [], []
    for mapped, row in enumerate(MATRIX):
        for truth, count in enumerate(row):
            reference += [truth] * count
            predicted += [mapped] * count
    return np.array(reference), np.array(predicted)


def test_confusion_matrix_rows_are_map_classes_and_columns_reference():
    reference, predicted = _labels()
    np.testing.assert_array_equal(confusionMatrix(reference, predicted, 3), MATRIX)


def test_hand_worked_example():
    report = assessAccuracy(*_labels(), ["A", "B", "C"])
    assert report.total == 30 and report.correct == 23
    assert report.overallAccuracy == pytest.approx(23 / 30)
    assert report.kappa == pytest.approx(0.65)
    np.testing.assert_allclose(report.producersAccuracy, [0.8, 0.6, 0.9])
    np.testing.assert_allclose(report.usersAccuracy, [0.8, 0.75, 0.75])
    np.testing.assert_allclose(report.omissionError, [0.2, 0.4, 0.1])
    np.testing.assert_allclose(report.commissionError, [0.2, 0.25, 0.25])
    np.testing.assert_array_equal(report.referenceTotals, [10, 10, 10])
    np.testing.assert_array_equal(report.mapTotals, [10, 8, 12])
    low, high = report.overallInterval
    assert low == pytest.approx(0.5907, abs=1e-4)
    assert high == pytest.approx(0.8821, abs=1e-4)


def test_wilson_interval_known_values():
    # 0 of 10: the interval still has width, unlike the normal approximation
    low, high = wilsonInterval(0, 10)
    assert low == 0.0 and high == pytest.approx(0.2775, abs=1e-4)
    assert wilsonInterval(5, 10) == pytest.approx((0.2366, 0.7634), abs=1e-4)
    assert all(math.isnan(v) for v in wilsonInterval(0, 0))


def test_undefined_measures_are_nan_and_none_in_the_dict():
    # class C never appears in the reference nor the map
    report = AccuracyReport(("A", "B", "C"), [[5, 1, 0], [0, 4, 0], [0, 0, 0]])
    assert math.isnan(report.producersAccuracy[2])
    assert math.isnan(report.usersAccuracy[2])
    entry = report.toDict()["perClass"][2]
    assert entry["producersAccuracy"] is None and entry["usersInterval"] == [
        None,
        None,
    ]


def test_perfect_agreement_of_one_class_has_undefined_kappa():
    report = AccuracyReport(("A", "B"), [[10, 0], [0, 0]])
    assert report.overallAccuracy == 1.0
    assert math.isnan(report.kappa)


def test_round_trips_through_its_dict():
    report = assessAccuracy(*_labels(), ["A", "B", "C"])
    data = report.toDict()
    assert data["overallAccuracy"] == pytest.approx(23 / 30)
    assert data["kappa"] == pytest.approx(0.65)
    assert "Wilson" in data["intervalMethod"]
    again = AccuracyReport.fromDict(data)
    assert again.classes == report.classes
    np.testing.assert_array_equal(again.matrix, report.matrix)


def test_csv_has_the_header_matrix_classes_and_summary():
    report = assessAccuracy(*_labels(), ["A", "B", "C"])
    text = report.csvText(["Class map: scene"])
    lines = text.splitlines()
    assert lines[0] == "# Class map: scene"
    assert lines[1].startswith("# Confusion matrix: rows = map")
    assert lines[2] == "Map \\ Reference,A,B,C,Total"
    assert lines[3] == "A,8,1,1,10"
    assert lines[6] == "Total,10,10,10,30"
    assert "B,10,8,6,0.6," in text
    assert "Overall accuracy,0.766667" in text
    assert "Kappa,0.65" in text


def test_labels_out_of_range_are_refused():
    with pytest.raises(ValueError, match="between 0"):
        confusionMatrix(np.array([0, 3]), np.array([0, 1]), 3)
