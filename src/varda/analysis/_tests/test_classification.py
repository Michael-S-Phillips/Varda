"""Training an MLP on a workspace's ROIs and classifying the whole image."""

import numpy as np
import pytest
from shapely.geometry import box

from varda.analysis.analysis import AnalysisContext
from varda.analysis.classification import MlpClassificationAnalysis
from varda.common.entities import Color, ROIMode, VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.rois.roi_collection import ROICollection

RED = Color(1.0, 0.0, 0.0, 0.5)
BLUE = Color(0.0, 0.0, 1.0, 0.5)


def _twoRegionImage(seed=0) -> VardaRaster:
    """Left half: spectra around 0.2; right half: around 0.6 (plus noise)."""
    rng = np.random.default_rng(seed)
    cube = np.empty((20, 40, 8))
    cube[:, :20, :] = 0.2 + 0.02 * rng.normal(size=(20, 20, 8))
    cube[:, 20:, :] = 0.6 + 0.02 * rng.normal(size=(20, 20, 8))
    cube[0, 0, :] = -1.0  # nodata pixel
    return VardaRaster(ArrayDataSource(cube, nodata=-1.0), name="scene")


def _rois() -> ROICollection:
    rois = ROICollection()  # pixel-space collection
    rois.addROI(box(2, 2, 8, 8), "dark", RED, ROIMode.RECTANGLE)
    rois.addROI(box(30, 10, 36, 16), "bright", BLUE, ROIMode.RECTANGLE)
    return rois


def _analysis(rois) -> MlpClassificationAnalysis:
    analysis = MlpClassificationAnalysis()
    analysis.epochs.set(100)
    analysis.setContext(AnalysisContext(rois=rois))
    return analysis


def test_needs_rois():
    assert MlpClassificationAnalysis.needsRois
    assert MlpClassificationAnalysis.category == "Classification"


def test_classifies_the_whole_image_from_two_training_rois():
    image = _twoRegionImage()
    result = _analysis(_rois()).run(image, lambda p, m: None)

    assert result.name == "scene MLP classes"
    assert result.bandNames == ["Class", "P(dark)", "P(bright)"]
    classes = result.getData()[:, :, 0]
    # class ids follow ROI order: 0 = dark, 1 = bright; far from the training boxes too
    assert np.all(classes[5:15, 1:19] == 0)
    assert np.all(classes[5:15, 21:39] == 1)
    assert np.isnan(classes[0, 0])  # nodata stays missing
    assert result.width == image.width and result.height == image.height


def test_class_names_are_recorded_in_the_metadata():
    result = _analysis(_rois()).run(_twoRegionImage(), lambda p, m: None)
    assert result.extraMetadata["classes"] == ["dark", "bright"]


def test_requires_at_least_two_rois():
    rois = ROICollection()
    rois.addROI(box(2, 2, 8, 8), "only", RED, ROIMode.RECTANGLE)
    with pytest.raises(ValueError, match="two ROIs"):
        _analysis(rois).run(_twoRegionImage(), lambda p, m: None)


def test_requires_a_context_with_rois():
    analysis = MlpClassificationAnalysis()
    with pytest.raises(ValueError, match="ROIs"):
        analysis.run(_twoRegionImage(), lambda p, m: None)
