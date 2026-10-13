"""Target and anomaly detection: RX (global and local), ACE, matched filter."""

import numpy as np
import pytest
from shapely.geometry import box

from varda.analysis.analysis import AnalysisContext
from varda.analysis.detection import (
    AceAnalysis,
    LocalRxAnalysis,
    MatchedFilterAnalysis,
    RxAnalysis,
)
from varda.analysis.registry import ANALYSES
from varda.common.entities import Color, ROIMode, VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.rois.roi_collection import ROICollection

BANDS = 12
TARGET = np.linspace(0.8, 0.2, BANDS)  # a distinctive declining spectrum


def _scene():
    """Smooth background with a 3x3 target patch at (20, 30) and a 3x3 anomaly
    (a different spectrum) at (8, 8)."""
    rng = np.random.default_rng(0)
    background = 0.4 + 0.05 * np.sin(np.linspace(0, 3, BANDS))
    cube = background + 0.01 * rng.normal(size=(32, 40, BANDS))
    cube[19:22, 29:32] = TARGET + 0.01 * rng.normal(size=(3, 3, BANDS))
    cube[7:10, 7:10] = np.linspace(0.1, 0.9, BANDS)
    cube[0, 0] = np.nan
    image = VardaRaster(
        ArrayDataSource(
            cube, wavelengths=np.linspace(1000, 2500, BANDS), wavelengthUnits="nm"
        ),
        name="scene",
    )
    return image, cube


def _peak(result) -> tuple[int, int]:
    data = result.getData()[:, :, 0]
    return np.unravel_index(np.nanargmax(data), data.shape)


@pytest.mark.parametrize("analysisClass", [RxAnalysis, LocalRxAnalysis])
def test_rx_finds_the_anomalies(analysisClass):
    image, _ = _scene()
    result = analysisClass().run(image, lambda p, m: None)
    r, c = _peak(result)
    assert (7 <= r <= 9 and 7 <= c <= 9) or (19 <= r <= 21 and 29 <= c <= 31)
    assert np.isnan(result.getData()[0, 0, 0])
    assert result.bandCount == 1


def _targetRois():
    rois = ROICollection()
    rois.addROI(
        box(29, 19, 32, 22), "target mineral", Color(1, 0, 0, 0.5), ROIMode.RECTANGLE
    )
    return rois


@pytest.mark.parametrize("analysisClass", [AceAnalysis, MatchedFilterAnalysis])
def test_target_detectors_light_up_the_target_class(analysisClass):
    image, _ = _scene()
    analysis = analysisClass()
    analysis.setContext(AnalysisContext(rois=_targetRois()))
    analysis.prepareFor(image)
    assert analysis.unavailableReason(image) == ""
    result = analysis.run(image, lambda p, m: None)
    assert result.bandNames == ["target mineral"]
    r, c = _peak(result)
    assert 19 <= r <= 21 and 29 <= c <= 31
    scores = result.getData()[:, :, 0]
    assert np.nanmedian(scores) < 0.5 * np.nanmax(scores)


def test_target_detectors_need_a_target_class():
    image, _ = _scene()
    analysis = AceAnalysis()
    analysis.setContext(AnalysisContext(rois=ROICollection()))
    analysis.prepareFor(image)
    assert "target" in analysis.unavailableReason(image).lower()


def test_the_detectors_are_offered_together():
    for cls in (RxAnalysis, LocalRxAnalysis, AceAnalysis, MatchedFilterAnalysis):
        assert cls in ANALYSES and cls.category == "Target Detection"
