"""Every new image processing analysis opens in the Run Analysis dialog and
runs with its default settings on a small image, as from the menu."""

import numpy as np
import pytest
from affine import Affine
from rasterio.crs import CRS

from varda.analysis.class_tools import classRaster, isClassMap
from varda.analysis.color_transforms import (
    ColorTransformAnalysis,
    DecorrelationStretchAnalysis,
    SaturationStretchAnalysis,
)
from varda.analysis.dialog import RunAnalysisDialog
from varda.analysis.geometry import ResampleAnalysis, RotateFlipAnalysis, SubsetAnalysis
from varda.analysis.registry import ANALYSES
from varda.analysis.spatial_filters import (
    CustomKernelAnalysis,
    EdgeDetectionAnalysis,
    FrequencyFilterAnalysis,
    MorphologyAnalysis,
    SharpeningAnalysis,
    SmoothingAnalysis,
    SpeckleFilterAnalysis,
)
from varda.analysis.class_tools import (
    ClumpAnalysis,
    DensitySliceAnalysis,
    MajorityFilterAnalysis,
    SieveAnalysis,
)
from varda.analysis.texture import CooccurrenceTextureAnalysis, LocalStatisticsAnalysis
from varda.analysis.topography import TerrainAnalysis
from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource

ON_IMAGES = [
    SmoothingAnalysis,
    SharpeningAnalysis,
    EdgeDetectionAnalysis,
    MorphologyAnalysis,
    SpeckleFilterAnalysis,
    FrequencyFilterAnalysis,
    CustomKernelAnalysis,
    LocalStatisticsAnalysis,
    CooccurrenceTextureAnalysis,
    ColorTransformAnalysis,
    DecorrelationStretchAnalysis,
    SaturationStretchAnalysis,
    DensitySliceAnalysis,
    TerrainAnalysis,
    ResampleAnalysis,
    RotateFlipAnalysis,
    SubsetAnalysis,
]
ON_CLASS_MAPS = [MajorityFilterAnalysis, SieveAnalysis, ClumpAnalysis]


def _image() -> VardaRaster:
    cube = np.random.default_rng(0).uniform(0.1, 0.5, (24, 30, 6)).astype(np.float32)
    cube[0, 0] = -1.0
    return VardaRaster(
        ArrayDataSource(
            cube,
            wavelengths=np.linspace(1000.0, 2500.0, 6),
            wavelengthUnits="Nanometers",
            transform=Affine(18.0, 0.0, 1000.0, 0.0, -18.0, 5000.0),
            crs=CRS.from_epsg(32612),
            nodata=-1.0,
            defaultBands=np.array([5, 3, 1]),
        ),
        name="scene",
    )


def _classMap() -> VardaRaster:
    classes = np.random.default_rng(1).integers(0, 3, (24, 30)).astype(float)
    return classRaster(
        _image(),
        classes,
        ["a", "b", "c"],
        ["#f00", "#0f0", "#00f"],
        name="classes",
        description="test",
    )


def test_they_are_all_in_the_processing_menu():
    for analysis in ON_IMAGES + ON_CLASS_MAPS:
        assert analysis in ANALYSES


@pytest.mark.parametrize(
    "analysis", ON_IMAGES + ON_CLASS_MAPS, ids=lambda a: a.analysisId
)
def test_each_opens_in_the_dialog_and_runs_with_defaults(qtbot, analysis):
    image = _classMap() if analysis in ON_CLASS_MAPS else _image()
    dialog = RunAnalysisDialog([image], [analysis], analysis=analysis)
    qtbot.addWidget(dialog)
    chosen = dialog.selectedAnalysis()
    assert isinstance(chosen, analysis)
    chosen.prepareFor(image)
    assert chosen.unavailableReason(image) == ""
    result = chosen.run(image, lambda percent, message: None)
    assert isinstance(result, VardaRaster) and result.name.startswith(image.name)
    if analysis in ON_CLASS_MAPS + [DensitySliceAnalysis]:
        assert isClassMap(result)


def test_class_map_tools_refuse_ordinary_images():
    for analysis in ON_CLASS_MAPS:
        assert analysis().unavailableReason(_image()) != ""
