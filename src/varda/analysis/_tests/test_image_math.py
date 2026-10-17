"""Image math: two images (or an image and a number) combined band by band,
masks made by thresholds, and masks applied, normally, inversely, or by
multiplying."""

import numpy as np
import pytest

from varda.analysis.analysis import AnalysisContext
from varda.analysis.image_math import (
    ApplyMaskAnalysis,
    ImageArithmeticAnalysis,
    MaskMode,
    Operation,
    ThresholdSide,
    ThresholdToMaskAnalysis,
)
from varda.analysis.registry import ANALYSES
from varda.common.entities import VardaRaster
from varda.common.vec2 import Vec2
from varda.image_loading.data_sources.array_data_source import ArrayDataSource


def _image(data, name, **kwargs):
    return VardaRaster(
        ArrayDataSource(np.asarray(data, np.float32), **kwargs), name=name
    )


def _cube():
    data = np.arange(2 * 3 * 2, dtype=np.float32).reshape(2, 3, 2) + 1
    data[0, 0, 0] = -1
    return _image(data, "cube", wavelengths=np.array([500.0, 600.0]), nodata=-1.0)


def _run(analysis, image, *others):
    analysis.setContext(AnalysisContext(images=[image, *others]))
    analysis.prepareFor(image)
    return analysis


def test_they_are_in_the_image_math_menu():
    for analysis in (
        ImageArithmeticAnalysis,
        ThresholdToMaskAnalysis,
        ApplyMaskAnalysis,
    ):
        assert analysis in ANALYSES and analysis.category == "Image Math"


@pytest.mark.parametrize(
    "operation, expected",
    [
        (Operation.ADD, lambda a, b: a + b),
        (Operation.SUBTRACT, lambda a, b: a - b),
        (Operation.MULTIPLY, lambda a, b: a * b),
        (Operation.DIVIDE, lambda a, b: a / b),
        (Operation.MINIMUM, np.minimum),
        (Operation.MAXIMUM, np.maximum),
    ],
)
def test_two_images_band_by_band(operation, expected):
    image = _cube()
    other = _image(np.full((2, 3, 2), 2.0), "two")
    analysis = _run(ImageArithmeticAnalysis(), image, other)
    analysis.operation.set(operation)
    analysis.second.set(other)
    result = analysis.run(image, lambda *_: None)
    a = np.asarray(image.getData(), float)
    np.testing.assert_allclose(result.getData()[1:], expected(a, 2.0)[1:])
    assert np.isnan(result.getData()[0, 0, 0])  # no data stays no data
    assert result.bandModel.centers is not None  # the wavelengths come along


def test_a_one_band_image_or_a_number_applies_to_every_band():
    image = _cube()
    weights = _image(np.full((2, 3, 1), 0.5), "weights")
    analysis = _run(ImageArithmeticAnalysis(), image, weights)
    analysis.operation.set(Operation.MULTIPLY)
    analysis.second.set(weights)
    np.testing.assert_allclose(
        analysis.run(image, lambda *_: None).getData()[1], image.getData()[1] * 0.5
    )
    analysis.second.clear()
    analysis.number.set(10.0)
    analysis.operation.set(Operation.DIVIDE)
    np.testing.assert_allclose(
        analysis.run(image, lambda *_: None).getData()[1], image.getData()[1] / 10
    )


def test_dividing_by_zero_is_no_data():
    image = _cube()
    analysis = _run(ImageArithmeticAnalysis(), image)
    analysis.operation.set(Operation.DIVIDE)
    analysis.number.set(0.0)
    assert np.isnan(analysis.run(image, lambda *_: None).getData()).all()


def test_a_threshold_makes_a_mask():
    image = _cube()  # band 2 holds 2, 4, ... 12
    analysis = _run(ThresholdToMaskAnalysis(), image)
    analysis.band.set(2)
    analysis.limits.set(Vec2(4.0, 8.0))
    mask = analysis.run(image, lambda *_: None).getData()[..., 0]
    np.testing.assert_array_equal(
        mask, (image.getData()[..., 1] >= 4) & (image.getData()[..., 1] <= 8)
    )
    analysis.side.set(ThresholdSide.OUTSIDE)
    analysis.band.set(1)
    outside = analysis.run(image, lambda *_: None).getData()[..., 0]
    assert np.isnan(outside[0, 0])  # band 1 has no data there
    np.testing.assert_array_equal(outside.ravel()[1:], [1, 0, 0, 1, 1])  # 3,5,7,9,11


@pytest.mark.parametrize(
    "mode, kept",
    [
        (MaskMode.KEEP_SET, [True, False]),
        (MaskMode.KEEP_UNSET, [False, True]),
    ],
)
def test_a_mask_keeps_or_drops_pixels(mode, kept):
    image = _cube()
    mask = _image(np.array([[[1], [0], [1]], [[0], [1], [0]]]), "mask")
    analysis = _run(ApplyMaskAnalysis(), image, mask)
    analysis.mask.set(mask)
    analysis.mode.set(mode)
    out = analysis.run(image, lambda *_: None).getData()
    assert np.isfinite(out[0, 2]).all() == kept[0]  # mask set there
    assert np.isfinite(out[0, 1]).all() == kept[1]  # mask not set there


def test_a_mask_can_multiply():
    image = _cube()
    weights = _image(np.full((2, 3, 1), 0.25), "w")
    analysis = _run(ApplyMaskAnalysis(), image, weights)
    analysis.mask.set(weights)
    analysis.mode.set(MaskMode.MULTIPLY)
    np.testing.assert_allclose(
        analysis.run(image, lambda *_: None).getData()[1], image.getData()[1] * 0.25
    )


def test_only_images_on_the_same_grid_are_offered():
    image = _cube()
    small = _image(np.ones((1, 1, 1)), "small")
    analysis = _run(ApplyMaskAnalysis(), image, small)
    assert analysis.mask.imageProvider() == []
    assert "mask" in analysis.unavailableReason(image).lower()
