"""Analyses that compute statistics or fits across bands leave the image's
bad bands out: a bad band filled from its neighbors is a linear combination
of them, which makes covariances (nearly) singular. Each analysis must give
the same result on an image with a bad band as on the image without it."""

import numpy as np
import pytest
from shapely.geometry import box

from varda.analysis import classification, mapping
from varda.analysis.analysis import Analysis, AnalysisContext
from varda.analysis.classification import (
    _RoiTrainingAnalysis,
    CnnClassificationAnalysis,
    MlpClassificationAnalysis,
    VitClassificationAnalysis,
)
from varda.analysis.derivatives import SpectralDerivativeAnalysis
from varda.analysis.detection import (
    AceAnalysis,
    LocalRxAnalysis,
    MatchedFilterAnalysis,
    RxAnalysis,
)
from varda.analysis.mapping import (
    MtmfAnalysis,
    PixelPurityAnalysis,
    SamMappingAnalysis,
    UnmixingAnalysis,
)
from varda.analysis.rasters import goodBands, readGoodBands
from varda.analysis.statistical_classifiers import (
    KMeansAnalysis,
    MahalanobisAnalysis,
    MaximumLikelihoodAnalysis,
)
from varda.analysis.statistics import SpectralEntropyAnalysis
from varda.common.entities import Color, ROIMode, VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.rois.roi_collection import ROICollection

BANDS = 10
BAD = 4  # an interior band
WAVELENGTHS = np.linspace(1000.0, 1900.0, BANDS)


def _cube() -> np.ndarray:
    rng = np.random.default_rng(0)
    x = np.linspace(0, 1, BANDS)
    a = 0.5 - 0.2 * np.exp(-0.5 * ((x - 0.3) / 0.1) ** 2)
    b = 0.2 + 0.4 * x
    fraction = np.clip(np.linspace(-0.3, 1.3, 30), 0, 1)[None, :].repeat(24, axis=0)
    cube = (1 - fraction)[..., None] * a + fraction[..., None] * b
    cube += 0.01 * rng.normal(size=cube.shape)
    cube[10:13, 14:17] = np.linspace(0.9, 0.1, BANDS)  # a target / anomaly
    cube[:, :, BAD] = 50.0 + rng.normal(size=cube.shape[:2])  # garbage
    return cube


def _withBadBand() -> VardaRaster:
    bbl = [0 if i == BAD else 1 for i in range(BANDS)]
    source = ArrayDataSource(
        _cube(),
        wavelengths=WAVELENGTHS,
        wavelengthUnits="nm",
        extraMetadata={"bbl": bbl, "fwhm": list(range(10, 10 + BANDS))},
    )
    return VardaRaster(source, name="scene")


def _withoutBadBand() -> VardaRaster:
    keep = [i for i in range(BANDS) if i != BAD]
    source = ArrayDataSource(
        _cube()[:, :, keep],
        wavelengths=WAVELENGTHS[keep],
        wavelengthUnits="nm",
    )
    return VardaRaster(source, name="scene")


def _rois() -> ROICollection:
    rois = ROICollection()
    rois.addROI(box(1, 2, 6, 10), "A", Color(1, 0, 0, 1), ROIMode.RECTANGLE)
    rois.addROI(box(24, 12, 29, 20), "B", Color(0, 0, 1, 1), ROIMode.RECTANGLE)
    rois.addROI(box(14, 10, 17, 13), "target", Color(0, 1, 0, 1), ROIMode.RECTANGLE)
    return rois


def _run(analysisClass: type[Analysis], image: VardaRaster) -> np.ndarray:
    analysis = analysisClass()
    analysis.setContext(AnalysisContext(rois=_rois()))
    analysis.prepareFor(image)
    if isinstance(analysis, (AceAnalysis, MatchedFilterAnalysis)):
        analysis.rois.set(["target"])
    elif isinstance(analysis, _RoiTrainingAnalysis):
        analysis.rois.set(["A", "B"])
    return analysis.run(image, lambda p, m: None).getData()


def test_good_bands_leave_out_the_bad_ones():
    image = _withBadBand()
    assert list(goodBands(image)) == [i for i in range(BANDS) if i != BAD]
    cube, valid, bands = readGoodBands(image)
    assert cube.shape == (24, 30, BANDS - 1) and valid.all()
    np.testing.assert_array_equal(cube, _withoutBadBand().getData())
    assert list(bands) == list(goodBands(image))


@pytest.mark.parametrize(
    "analysisClass",
    [
        RxAnalysis,
        LocalRxAnalysis,
        AceAnalysis,
        MatchedFilterAnalysis,
        MaximumLikelihoodAnalysis,
        MahalanobisAnalysis,
        KMeansAnalysis,
        MlpClassificationAnalysis,
        SamMappingAnalysis,
        UnmixingAnalysis,
        MtmfAnalysis,
        SpectralEntropyAnalysis,
    ],
)
def test_cross_band_analyses_ignore_bad_bands(analysisClass):
    withBad = _run(analysisClass, _withBadBand())
    without = _run(analysisClass, _withoutBadBand())
    np.testing.assert_allclose(withBad, without, rtol=1e-4, atol=1e-5)


def test_spectral_derivative_covers_only_the_good_bands():
    image = _withBadBand()
    result = SpectralDerivativeAnalysis().run(image, lambda p, m: None)
    expected = SpectralDerivativeAnalysis().run(_withoutBadBand(), lambda p, m: None)
    assert result.bandCount == BANDS - 1
    np.testing.assert_allclose(
        np.asarray(result.wavelengths, float), np.asarray(expected.wavelengths, float)
    )
    np.testing.assert_allclose(result.getData(), expected.getData(), rtol=1e-6)
    assert not result.bandModel.badBands.any()
    assert result.extraMetadata["fwhm"] == [10 + i for i in range(BANDS) if i != BAD]


def test_pixel_purity_projects_only_good_bands(monkeypatch):
    seen = []

    def fakePpi(X, iterations, threshold, progress=None):
        seen.append(X)
        return np.zeros(X.shape[0])

    monkeypatch.setattr(mapping, "pixelPurityIndex", fakePpi)
    for image in (_withBadBand(), _withoutBadBand()):
        analysis = PixelPurityAnalysis()
        analysis.prepareFor(image)
        analysis.components.set(6)
        analysis.run(image, lambda p, m: None)
    np.testing.assert_array_equal(seen[0], seen[1])


@pytest.mark.parametrize(
    "analysisClass", [CnnClassificationAnalysis, VitClassificationAnalysis]
)
def test_patch_classifiers_train_on_good_bands(monkeypatch, analysisClass):
    seen = []

    class FakeJob:
        @staticmethod
        def trainAndClassify(cube, valid, rows, cols, y, classes, spec, progress):
            seen.append(cube.shape[2])
            return np.full((int(valid.sum()), classes), 1 / classes), 0.0

    monkeypatch.setattr(classification, "TORCH_AVAILABLE", True)
    monkeypatch.setattr(classification, "torch_job", FakeJob)
    _run(analysisClass, _withBadBand())
    assert seen == [BANDS - 1]
