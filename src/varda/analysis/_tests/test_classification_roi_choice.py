"""Classifiers train on the ROIs the user ticks, one class each."""

import numpy as np
import pytest
from shapely.geometry import box

from varda.analysis.analysis import AnalysisContext
from varda.analysis.classification import (
    CnnClassificationAnalysis,
    MlpClassificationAnalysis,
    VitClassificationAnalysis,
)
from varda.common.entities import Color, ROIMode, VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.rois.roi_collection import ROICollection

RED = Color(1.0, 0.0, 0.0, 0.5)


def _threeRegionImage() -> VardaRaster:
    rng = np.random.default_rng(0)
    cube = np.empty((20, 60, 8))
    cube[:, :20, :] = 0.2 + 0.02 * rng.normal(size=(20, 20, 8))
    cube[:, 20:40, :] = 0.5 + 0.02 * rng.normal(size=(20, 20, 8))
    cube[:, 40:, :] = 0.8 + 0.02 * rng.normal(size=(20, 20, 8))
    return VardaRaster(ArrayDataSource(cube), name="scene")


def _rois(names=("dark", "mid", "bright")) -> ROICollection:
    rois = ROICollection()
    for i, name in enumerate(names):
        left = 2 + 20 * i
        rois.addROI(box(left, 2, left + 6, 8), name, RED, ROIMode.RECTANGLE)
    return rois


@pytest.mark.parametrize(
    "analysisClass",
    [MlpClassificationAnalysis, CnnClassificationAnalysis, VitClassificationAnalysis],
)
def test_preparing_offers_the_workspace_rois_all_selected(analysisClass):
    analysis = analysisClass()
    analysis.setContext(AnalysisContext(rois=_rois()))

    analysis.prepareFor(_threeRegionImage())

    assert analysis.rois.choices == ["dark", "mid", "bright"]
    assert analysis.rois.get() == ["dark", "mid", "bright"]


def test_rois_with_the_same_name_are_told_apart():
    analysis = MlpClassificationAnalysis()
    analysis.setContext(AnalysisContext(rois=_rois(("rock", "rock", "soil"))))

    analysis.prepareFor(_threeRegionImage())

    assert analysis.rois.choices == ["rock (ROI 0)", "rock (ROI 1)", "soil"]


def test_fewer_than_two_selected_rois_is_refused_with_a_reason():
    image = _threeRegionImage()
    analysis = MlpClassificationAnalysis()
    analysis.setContext(AnalysisContext(rois=_rois()))
    analysis.prepareFor(image)
    assert analysis.unavailableReason(image) == ""

    analysis.rois.set(["mid"])

    assert "two" in analysis.unavailableReason(image)
    with pytest.raises(ValueError, match="two"):
        analysis.run(image, lambda p, m: None)


def test_training_uses_only_the_selected_rois():
    image = _threeRegionImage()
    analysis = MlpClassificationAnalysis()
    analysis.setContext(AnalysisContext(rois=_rois()))
    analysis.prepareFor(image)
    analysis.rois.set(["dark", "bright"])
    analysis.epochs.set(150)

    result = analysis.run(image, lambda p, m: None)

    assert result.extraMetadata["classes"] == ["dark", "bright"]
    assert result.bandNames == ["Class", "P(dark)", "P(bright)"]
    classes = result.getData()[:, :, 0]
    assert np.mean(classes[:, 2:18] == 0) > 0.95
    assert np.mean(classes[:, 42:58] == 1) > 0.95


def test_without_preparing_every_roi_is_used():
    image = _threeRegionImage()
    analysis = MlpClassificationAnalysis()
    analysis.setContext(AnalysisContext(rois=_rois()))
    analysis.epochs.set(50)

    result = analysis.run(image, lambda p, m: None)

    assert result.extraMetadata["classes"] == ["dark", "mid", "bright"]
