"""Processing > Endmembers: PPI and mapping the mean spectra of ROIs."""

import numpy as np
import pytest
from shapely.geometry import box

from varda.analysis.analysis import AnalysisContext
from varda.analysis.mapping import (
    MtmfAnalysis,
    PixelPurityAnalysis,
    SamMappingAnalysis,
    UnmixingAnalysis,
)
from varda.analysis.registry import ANALYSES
from varda.common.entities import Color, ROIMode, VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.rois.roi_collection import ROICollection


def _scene() -> tuple[VardaRaster, np.ndarray]:
    """Left half mostly endmember A, right half mostly B, smooth mixing."""
    rng = np.random.default_rng(0)
    x = np.linspace(0, 1, 30)
    A = 0.5 - 0.2 * np.exp(-0.5 * ((x - 0.3) / 0.05) ** 2)
    B = 0.2 + 0.4 * x
    fraction = np.clip(np.linspace(-0.3, 1.3, 40), 0, 1)[None, :].repeat(20, axis=0)
    cube = (1 - fraction)[..., None] * A + fraction[..., None] * B
    cube += 0.002 * rng.normal(size=cube.shape)
    cube[0, 0] = -1.0
    image = VardaRaster(ArrayDataSource(cube, nodata=-1.0), name="scene")
    return image, fraction


def _rois() -> ROICollection:
    rois = ROICollection()
    rois.addROI(box(1, 2, 5, 8), "A", Color(1.0, 0.0, 0.0, 1.0), ROIMode.RECTANGLE)
    rois.addROI(box(35, 10, 39, 16), "B", Color(0.0, 0.0, 1.0, 1.0), ROIMode.RECTANGLE)
    return rois


def _with(analysis):
    analysis.setContext(AnalysisContext(rois=_rois()))
    return analysis


def test_endmember_analyses_are_registered_together():
    for analysis in (
        PixelPurityAnalysis,
        SamMappingAnalysis,
        UnmixingAnalysis,
        MtmfAnalysis,
    ):
        assert analysis in ANALYSES and analysis.category == "Endmembers"
    assert SamMappingAnalysis.needsRois and not PixelPurityAnalysis.needsRois


def test_sam_classifies_each_half_and_records_roi_colours():
    image, _ = _scene()
    result = _with(SamMappingAnalysis()).run(image, lambda p, m: None)
    assert result.bandNames == ["Class", "Angle(A)", "Angle(B)"]
    classes = result.getData()[:, :, 0]
    assert np.all(classes[5:15, 1:8] == 0) and np.all(classes[5:15, 33:39] == 1)
    assert np.isnan(classes[0, 0])
    assert result.extraMetadata["classColors"] == ["#ff0000", "#0000ff"]


def test_unmixing_recovers_the_mixing_fraction():
    image, fraction = _scene()
    result = _with(UnmixingAnalysis()).run(image, lambda p, m: None)
    assert result.bandNames == ["A", "B", "RMS Error"]
    b = result.getData()[1:, 1:, 1]
    assert np.abs(b - fraction[1:, 1:]).mean() < 0.03


def test_mtmf_scores_the_b_half():
    image, fraction = _scene()
    analysis = _with(MtmfAnalysis())
    analysis.components.set(4)
    result = analysis.run(image, lambda p, m: None)
    assert result.bandNames == [
        "MF(A)",
        "MF(B)",
        "Infeasibility(A)",
        "Infeasibility(B)",
    ]
    mf = result.getData()[:, :, 1]
    # scores are relative to the scene mean (here a 50/50 mixture): pure B is
    # ~1, the mean-like middle ~0, and pure A lies the other way (~-1)
    assert mf[10, 37] == pytest.approx(1.0, abs=0.25)
    assert mf[10, 20] == pytest.approx(0.0, abs=0.25)
    assert mf[10, 2] < -0.5


def test_mapping_needs_two_rois():
    image, _ = _scene()
    analysis = _with(SamMappingAnalysis())
    analysis.prepareFor(image)
    analysis.rois.set(["A"])
    with pytest.raises(ValueError, match="at least two ROIs"):
        analysis.run(image, lambda p, m: None)


def test_ppi_analysis_counts_extreme_pixels():
    image, _ = _scene()
    analysis = PixelPurityAnalysis()
    analysis.prepareFor(image)
    analysis.components.set(3)
    analysis.iterations.set(500)
    analysis.threshold.set(0.01)
    result = analysis.run(image, lambda p, m: None)
    ppi = result.getData()[:, :, 0]
    assert result.bandNames == ["PPI"]
    assert np.isnan(ppi[0, 0]) and np.nanmax(ppi) > 0
