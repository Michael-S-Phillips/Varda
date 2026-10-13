"""Gaussian maximum likelihood, Mahalanobis distance and k-means classifiers."""

import numpy as np
import pytest
from shapely.geometry import box

from varda.analysis.analysis import AnalysisContext
from varda.analysis.registry import ANALYSES
from varda.analysis.statistical_classifiers import (
    KMeansAnalysis,
    MahalanobisAnalysis,
    MaximumLikelihoodAnalysis,
)
from varda.common.entities import Color, ROIMode, VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.rois.roi_collection import ROICollection

RED, BLUE = Color(1, 0, 0, 0.5), Color(0, 0, 1, 0.5)


def _scene(bands=6):
    rng = np.random.default_rng(1)
    cube = np.empty((30, 40, bands))
    cube[:, :20] = 0.3 + 0.02 * rng.normal(size=(30, 20, bands))
    cube[:, 20:] = np.linspace(0.6, 0.2, bands) + 0.02 * rng.normal(
        size=(30, 20, bands)
    )
    cube[0, 0] = np.nan
    return VardaRaster(ArrayDataSource(cube), name="scene")


def _rois(size=6):
    rois = ROICollection()
    rois.addROI(box(2, 2, 2 + size, 2 + size), "dark", RED, ROIMode.RECTANGLE)
    rois.addROI(box(25, 10, 25 + size, 10 + size), "bright", BLUE, ROIMode.RECTANGLE)
    return rois


@pytest.mark.parametrize("cls", [MaximumLikelihoodAnalysis, MahalanobisAnalysis])
def test_supervised_classifiers_separate_the_two_materials(cls):
    analysis = cls()
    analysis.setContext(AnalysisContext(rois=_rois()))
    analysis.prepareFor(_scene())
    result = analysis.run(_scene(), lambda p, m: None)
    assert result.bandNames == ["Class", "P(dark)", "P(bright)"]
    classes = result.getData()[:, :, 0]
    assert np.mean(classes[:, :18] == 0) > 0.95 and np.mean(classes[:, 22:] == 1) > 0.95
    assert np.isnan(classes[0, 0])
    assert result.extraMetadata["classColors"] == ["#ff0000", "#0000ff"]
    probabilities = result.getData()[1:, :, 1:]
    np.testing.assert_allclose(probabilities.sum(axis=2), 1.0, atol=1e-6)


def test_small_classes_on_many_bands_are_reduced_not_dropped():
    """SPy drops classes with fewer pixels than bands; Varda reduces first."""
    image = _scene(bands=60)
    analysis = MaximumLikelihoodAnalysis()
    analysis.setContext(AnalysisContext(rois=_rois(size=4)))  # 16 pixels per class
    result = analysis.run(image, lambda p, m: None)
    assert result.extraMetadata["classes"] == ["dark", "bright"]
    assert 2 <= result.extraMetadata["components"] < 16


def test_a_class_too_small_to_train_is_a_clear_error():
    rois = ROICollection()
    rois.addROI(box(2, 2, 3, 3), "speck", RED, ROIMode.RECTANGLE)  # one pixel
    rois.addROI(box(25, 10, 31, 16), "bright", BLUE, ROIMode.RECTANGLE)
    analysis = MaximumLikelihoodAnalysis()
    analysis.setContext(AnalysisContext(rois=rois))
    with pytest.raises(ValueError, match="speck"):
        analysis.run(_scene(), lambda p, m: None)


def test_kmeans_groups_the_scene_without_rois():
    analysis = KMeansAnalysis()
    analysis.clusters.set(2)
    result = analysis.run(_scene(), lambda p, m: None)
    assert result.bandNames[0] == "Class"
    classes = result.getData()[:, :, 0]
    left, right = classes[1:, :18], classes[:, 22:]
    assert len(np.unique(left)) == 1 and len(np.unique(right)) == 1
    assert np.unique(left) != np.unique(right)
    assert result.extraMetadata["classes"] == ["Cluster 1", "Cluster 2"]
    assert len(result.extraMetadata["classColors"]) == 2


def test_the_classifiers_are_offered():
    for cls in (MaximumLikelihoodAnalysis, MahalanobisAnalysis, KMeansAnalysis):
        assert cls in ANALYSES and cls.category == "Classification"
