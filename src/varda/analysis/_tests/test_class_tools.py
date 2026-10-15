"""Density slice and the class map clean-up tools."""

import numpy as np
import pytest

from varda.analysis.class_tools import (
    ClumpAnalysis,
    Connectivity,
    DensitySliceAnalysis,
    MajorityFilterAnalysis,
    MajorityRule,
    SieveAnalysis,
    SliceMode,
    classRaster,
    isClassMap,
)
from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource

QUIET = lambda percent, message: None  # noqa: E731
NAMES, COLORS = ["water", "rock", "dust"], ["#0000ff", "#888888", "#ffaa00"]


def _scene(classes: np.ndarray) -> VardaRaster:
    base = VardaRaster(
        ArrayDataSource(np.zeros(classes.shape + (1,), np.float32)), name="scene"
    )
    return classRaster(base, classes, NAMES, COLORS, name="classes", description="test")


def _classes(result: VardaRaster) -> np.ndarray:
    return np.asarray(result.getData(), float)[:, :, 0]


def test_class_maps_are_recognized_and_other_images_refused():
    plain = VardaRaster(ArrayDataSource(np.zeros((4, 4, 3), np.float32)), name="plain")
    assert isClassMap(_scene(np.zeros((4, 4))))
    assert "class map" in SieveAnalysis().unavailableReason(plain)


def test_majority_removes_speckle_and_keeps_names_and_colors():
    classes = np.zeros((9, 9))
    classes[4, 4] = 1  # one speck of rock in water
    result = MajorityFilterAnalysis().run(_scene(classes), QUIET)
    assert np.all(_classes(result) == 0)
    assert result.extraMetadata["classes"] == NAMES
    assert result.extraMetadata["classColors"] == COLORS


def test_minority_brings_out_the_rare_class():
    classes = np.zeros((9, 9))
    classes[4, 4] = 1
    analysis = MajorityFilterAnalysis()
    analysis.rule.set(MajorityRule.MINORITY)
    out = _classes(analysis.run(_scene(classes), QUIET))
    assert np.all(out[3:6, 3:6] == 1)


def test_a_heavy_center_weight_keeps_the_original():
    classes = np.zeros((9, 9))
    classes[4, 4] = 1
    analysis = MajorityFilterAnalysis()
    analysis.centerWeight.set(9)
    assert _classes(analysis.run(_scene(classes), QUIET))[4, 4] == 1


def test_unclassified_pixels_stay_unclassified():
    classes = np.zeros((6, 6))
    classes[2, 2] = np.nan
    assert np.isnan(
        _classes(MajorityFilterAnalysis().run(_scene(classes), QUIET))[2, 2]
    )


def test_sieve_removes_small_groups_or_fills_them():
    classes = np.zeros((10, 10))
    classes[1, 1] = 1  # a group of 1
    classes[5:8, 5:8] = 2  # a group of 9
    analysis = SieveAnalysis()
    analysis.minimum.set(4)
    out = _classes(analysis.run(_scene(classes), QUIET))
    assert np.isnan(out[1, 1]) and np.all(out[5:8, 5:8] == 2)
    analysis.fill.set(True)
    assert _classes(analysis.run(_scene(classes), QUIET))[1, 1] == 0


def test_sieve_connectivity_decides_whether_diagonal_pixels_join():
    classes = np.zeros((6, 6))
    classes[1, 1] = classes[2, 2] = 1  # touching only at a corner
    analysis = SieveAnalysis()
    analysis.minimum.set(2)
    analysis.connectivity.set(Connectivity.FOUR)
    assert np.isnan(_classes(analysis.run(_scene(classes), QUIET))[1, 1])
    analysis.connectivity.set(Connectivity.EIGHT)
    assert _classes(analysis.run(_scene(classes), QUIET))[1, 1] == 1


def test_clump_fills_holes_but_keeps_solid_regions_of_other_classes():
    classes = np.zeros((12, 12))
    classes[:, 6:] = 1  # a solid rock region
    classes[3, 2] = np.nan  # a hole in the water
    classes[8, 3] = 2  # a speck of dust in the water
    out = _classes(ClumpAnalysis().run(_scene(classes), QUIET))
    assert out[3, 2] == 0 and out[8, 3] == 0
    assert np.all(out[:, 7:] == 1)


def _band(values: np.ndarray) -> VardaRaster:
    return VardaRaster(
        ArrayDataSource(values.astype(np.float32)[:, :, None]), name="band"
    )


def test_equal_interval_slices_between_low_and_high():
    values = np.tile(np.linspace(0.0, 1.0, 10), (3, 1))
    analysis = DensitySliceAnalysis()
    analysis.slices.set(5)
    analysis.low.set(0.0)
    analysis.high.set(1.0)
    result = analysis.run(_band(values), QUIET)
    out = _classes(result)
    assert out[0, 0] == 0 and out[0, -1] == 4
    assert result.extraMetadata["classes"][0] == "0 – 0.2"
    assert len(result.extraMetadata["classColors"]) == 5


def test_quantile_slices_have_equal_counts():
    values = np.random.default_rng(0).exponential(size=(40, 40))
    analysis = DensitySliceAnalysis()
    analysis.slices.set(4)
    analysis.mode.set(SliceMode.QUANTILE)
    counts = np.bincount(
        _classes(analysis.run(_band(values), QUIET)).astype(int).ravel()
    )
    assert counts.tolist() == pytest.approx([400] * 4, abs=2)
