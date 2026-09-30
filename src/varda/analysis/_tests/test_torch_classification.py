"""CNN and ViT classifiers trained on ROI patches (optional PyTorch extra)."""

import numpy as np
import pytest
from shapely.geometry import box

from varda.analysis.analysis import AnalysisContext
from varda.analysis.classification import (
    CnnClassificationAnalysis,
    VitClassificationAnalysis,
)
from varda.common.entities import Color, ROIMode, VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.rois.roi_collection import ROICollection

RED = Color(1.0, 0.0, 0.0, 0.5)
BLUE = Color(0.0, 0.0, 1.0, 0.5)


def _twoRegionImage(seed=0) -> VardaRaster:
    rng = np.random.default_rng(seed)
    cube = np.empty((20, 40, 8))
    cube[:, :20, :] = 0.2 + 0.02 * rng.normal(size=(20, 20, 8))
    cube[:, 20:, :] = 0.6 + 0.02 * rng.normal(size=(20, 20, 8))
    cube[0, 0, :] = -1.0
    return VardaRaster(ArrayDataSource(cube, nodata=-1.0), name="scene")


def _rois() -> ROICollection:
    rois = ROICollection()
    rois.addROI(box(2, 2, 8, 8), "dark", RED, ROIMode.RECTANGLE)
    rois.addROI(box(30, 10, 36, 16), "bright", BLUE, ROIMode.RECTANGLE)
    return rois


def test_torch_classifiers_are_filed_under_classification_and_need_rois():
    for analysis in (CnnClassificationAnalysis, VitClassificationAnalysis):
        assert analysis.category == "Classification"
        assert analysis.needsRois
        assert analysis.requirement == "PyTorch"


def test_unavailable_without_torch(monkeypatch):
    from varda.analysis import classification

    monkeypatch.setattr(classification, "TORCH_AVAILABLE", False)
    assert not CnnClassificationAnalysis.isAvailable()
    assert not VitClassificationAnalysis.isAvailable()


@pytest.mark.parametrize(
    "analysisClass, suffix",
    [
        (CnnClassificationAnalysis, "CNN classes"),
        (VitClassificationAnalysis, "ViT classes"),
    ],
)
def test_classifies_the_two_regions_from_roi_patches(analysisClass, suffix):
    pytest.importorskip("torch")
    image = _twoRegionImage()
    analysis = analysisClass()
    analysis.epochs.set(40)
    analysis.patchSize.set(3)
    analysis.setContext(AnalysisContext(rois=_rois()))

    result = analysis.run(image, lambda p, m: None)

    assert result.name == f"scene {suffix}"
    assert result.bandNames == ["Class", "P(dark)", "P(bright)"]
    classes = result.getData()[:, :, 0]
    assert np.mean(classes[3:17, 2:18] == 0) > 0.95
    assert np.mean(classes[3:17, 22:38] == 1) > 0.95
    assert np.isnan(classes[0, 0])
    assert result.extraMetadata["classes"] == ["dark", "bright"]
