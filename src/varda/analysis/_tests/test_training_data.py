"""Training and hold-out validation pixels from ROI classes, and the
supervised classifiers' hold-out validation."""

import numpy as np
import pytest
from shapely.geometry import box

from varda.analysis.analysis import AnalysisContext
from varda.analysis.classification import (
    MlpClassificationAnalysis,
    VitClassificationAnalysis,
)
from varda.analysis.statistical_classifiers import (
    MahalanobisAnalysis,
    MaximumLikelihoodAnalysis,
)
from varda.analysis.training_data import collectTrainingData, heldOutCount
from varda.common.entities import Color, ROIMode, VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.rois.roi_collection import ROICollection

RED, BLUE = Color(1.0, 0.0, 0.0, 0.5), Color(0.0, 0.0, 1.0, 0.5)


def _image() -> VardaRaster:
    """Left half: spectra around 0.2; right half: around 0.6."""
    rng = np.random.default_rng(0)
    cube = np.empty((20, 40, 6))
    cube[:, :20] = 0.2 + 0.02 * rng.normal(size=(20, 20, 6))
    cube[:, 20:] = np.linspace(0.7, 0.4, 6) + 0.02 * rng.normal(size=(20, 20, 6))
    return VardaRaster(ArrayDataSource(cube), name="scene")


def _rois() -> ROICollection:
    """Four 3×3 ROIs of each class (36 pixels each)."""
    rois = ROICollection()
    for x, y in [(1, 1), (6, 1), (1, 10), (6, 10)]:
        rois.addROI(box(x, y, x + 3, y + 3), "dark", RED, ROIMode.RECTANGLE)
    for x, y in [(25, 1), (31, 1), (25, 10), (31, 10)]:
        rois.addROI(box(x, y, x + 3, y + 3), "bright", BLUE, ROIMode.RECTANGLE)
    return rois


def _valid() -> np.ndarray:
    return np.ones((20, 40), dtype=bool)


@pytest.mark.parametrize(
    "rois, fraction, expected",
    [(4, 0.25, 1), (4, 0.5, 2), (4, 0.9, 3), (1, 0.5, 0), (2, 0.1, 1), (5, 0.0, 0)],
)
def test_held_out_count(rois, fraction, expected):
    assert heldOutCount(rois, fraction) == expected


def test_holds_out_whole_rois_per_class():
    data = collectTrainingData(
        _rois(), _image(), _valid(), ["dark", "bright"], holdOut=0.25, seed=3
    )
    for entry in data.record["classes"]:
        assert entry["rois"] == 4 and entry["validationRois"] == 1
        assert entry["trainingPixels"] == 27 and entry["validationPixels"] == 9
        assert len(entry["heldOutRoiNumbers"]) == 1
    # no pixel is both training and validation
    train = set(zip(data.rows.tolist(), data.cols.tolist()))
    held = set(zip(data.validationRows.tolist(), data.validationCols.tolist()))
    assert not train & held
    assert data.hasValidation


def test_the_seed_picks_the_held_out_rois_reproducibly():
    def picks(seed):
        data = collectTrainingData(
            _rois(), _image(), _valid(), ["dark", "bright"], holdOut=0.5, seed=seed
        )
        return [e["heldOutRoiNumbers"] for e in data.record["classes"]]

    assert picks(1) == picks(1)
    assert any(picks(1) != picks(s) for s in range(2, 8))


def test_a_class_with_one_roi_trains_only_and_says_so():
    rois = _rois()
    rois.addROI(box(14, 16, 18, 19), "dust", RED, ROIMode.RECTANGLE)
    data = collectTrainingData(
        rois, _image(), _valid(), ["dark", "bright", "dust"], holdOut=0.5
    )
    dust = data.record["classes"][2]
    assert dust["validationRois"] == 0 and dust["trainingPixels"] == 12
    assert any("dust" in note and "only one ROI" in note for note in data.notes)


def test_pixels_in_rois_of_two_classes_are_left_out_and_counted():
    rois = ROICollection()
    rois.addROI(box(0, 0, 4, 4), "dark", RED, ROIMode.RECTANGLE)  # 16 pixels
    rois.addROI(box(2, 0, 6, 4), "bright", BLUE, ROIMode.RECTANGLE)  # 8 shared
    data = collectTrainingData(rois, _image(), _valid(), ["dark", "bright"])
    assert data.record["ambiguousPixels"] == 8
    assert [e["trainingPixels"] for e in data.record["classes"]] == [8, 8]
    assert set(data.cols[data.labels == 0].tolist()) == {0, 1}
    assert set(data.cols[data.labels == 1].tolist()) == {4, 5}
    assert any("8 pixels" in note for note in data.notes)


def test_overlap_within_a_class_is_not_ambiguous():
    rois = ROICollection()
    rois.addROI(box(0, 0, 4, 4), "dark", RED, ROIMode.RECTANGLE)
    rois.addROI(box(2, 0, 6, 4), "dark", RED, ROIMode.RECTANGLE)
    rois.addROI(box(30, 0, 34, 4), "bright", BLUE, ROIMode.RECTANGLE)
    data = collectTrainingData(rois, _image(), _valid(), ["dark", "bright"])
    assert data.record["ambiguousPixels"] == 0
    assert data.record["classes"][0]["trainingPixels"] == 24


@pytest.mark.parametrize(
    "analysisClass",
    [MlpClassificationAnalysis, MaximumLikelihoodAnalysis, MahalanobisAnalysis],
)
def test_classifiers_report_hold_out_accuracy(analysisClass):
    analysis = analysisClass()
    analysis.setContext(AnalysisContext(rois=_rois()))
    analysis.holdOut.set(0.25)
    if isinstance(analysis, MlpClassificationAnalysis):
        analysis.epochs.set(60)
    result = analysis.run(_image(), lambda p, m: None)

    validation = result.extraMetadata["validation"]
    report = validation["report"]
    assert report["totalPixels"] == 18  # one 3×3 ROI per class
    assert report["overallAccuracy"] == pytest.approx(1.0)
    assert validation["referenceRois"] == {
        "dark": {"rois": 1, "pixels": 9},
        "bright": {"rois": 1, "pixels": 9},
    }
    training = result.extraMetadata["trainingData"]
    assert [e["trainingPixels"] for e in training["classes"]] == [27, 27]
    assert "hold-out accuracy 100.0%" in result.dataSource.description


def test_without_hold_out_there_is_no_validation_but_the_counts_are_kept():
    analysis = MaximumLikelihoodAnalysis()
    analysis.setContext(AnalysisContext(rois=_rois()))
    result = analysis.run(_image(), lambda p, m: None)
    assert "validation" not in result.extraMetadata
    assert [
        e["trainingPixels"] for e in result.extraMetadata["trainingData"]["classes"]
    ] == [36, 36]


def test_vit_refuses_heads_that_do_not_divide_the_embedding():
    analysis = VitClassificationAnalysis()
    analysis.setContext(AnalysisContext(rois=_rois()))
    analysis.embedDim.set(64)
    analysis.heads.set(5)
    reason = analysis.unavailableReason(_image())
    assert "Embedding Size (64)" in reason and "Attention Heads (5)" in reason
    with pytest.raises(ValueError, match="multiple of Attention Heads"):
        analysis.run(_image(), lambda p, m: None)
    analysis.heads.set(8)
    assert analysis.unavailableReason(_image()) == ""
