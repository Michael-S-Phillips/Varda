"""Color transforms, the decorrelation stretch and the saturation stretch."""

import numpy as np
import pytest

from varda.analysis.color_transforms import (
    ColorSpace,
    ColorTransformAnalysis,
    DecorrelationStretchAnalysis,
    SaturationStretchAnalysis,
    hlsToRgb,
    rgbToHls,
)
from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource

QUIET = lambda percent, message: None  # noqa: E731
RNG = np.random.default_rng(0)


def _image(cube, defaultBands=None) -> VardaRaster:
    wavelengths = np.linspace(500.0, 900.0, cube.shape[2])
    return VardaRaster(
        ArrayDataSource(
            cube.astype(np.float32), wavelengths=wavelengths, defaultBands=defaultBands
        ),
        name="scene",
    )


def test_hls_round_trip():
    rgb = RNG.uniform(size=(50, 3))
    assert np.allclose(hlsToRgb(rgbToHls(rgb)), rgb, atol=1e-9)
    gray = np.full((1, 3), 0.4)
    assert np.allclose(rgbToHls(gray), [[0.0, 0.4, 0.0]])


@pytest.mark.parametrize(
    ("forward", "back"),
    [
        (ColorSpace.RGB_TO_HSV, ColorSpace.HSV_TO_RGB),
        (ColorSpace.RGB_TO_HLS, ColorSpace.HLS_TO_RGB),
    ],
)
def test_forward_then_back_gives_the_stretched_rgb(forward, back):
    cube = RNG.uniform(0.1, 0.9, size=(20, 20, 3))
    analysis = ColorTransformAnalysis()
    analysis.direction.set(forward)
    hues = analysis.run(_image(cube), QUIET)
    assert hues.bandNames[0] == "Hue"
    analysis.direction.set(back)
    rgb = np.asarray(analysis.run(hues, QUIET).getData(), float)
    stretched = np.stack(
        [
            np.clip((c - np.percentile(c, 2)) / np.ptp(np.percentile(c, [2, 98])), 0, 1)
            for c in np.moveaxis(cube, 2, 0)
        ],
        axis=-1,
    )
    assert np.allclose(rgb, stretched, atol=1e-5)


def test_the_bands_default_to_the_display_bands():
    analysis = DecorrelationStretchAnalysis()
    analysis.prepareFor(_image(np.zeros((4, 4, 6)), defaultBands=np.array([5, 3, 1])))
    assert (analysis.red.value, analysis.green.value, analysis.blue.value) == (6, 4, 2)
    assert "three bands" in analysis.unavailableReason(_image(np.zeros((4, 4, 2))))


def test_decorrelation_stretch_decorrelates_and_keeps_mean_and_spread():
    base = RNG.normal(size=(40, 40))
    cube = np.stack(
        [base + 0.1 * RNG.normal(size=base.shape) * k for k in (1, 2, 3)], axis=-1
    )  # three highly correlated bands
    out = np.asarray(
        DecorrelationStretchAnalysis().run(_image(cube), QUIET).getData(), float
    )
    pixels, original = out.reshape(-1, 3), cube.reshape(-1, 3)
    correlation = np.corrcoef(pixels, rowvar=False)
    assert np.allclose(correlation, np.eye(3), atol=1e-4)
    assert np.allclose(pixels.mean(0), original.mean(0), atol=1e-4)
    assert np.allclose(pixels.std(0), original.std(0), rtol=1e-3)


def test_saturation_stretch_raises_saturation():
    gray = RNG.uniform(0.3, 0.7, size=(30, 30, 1))
    cube = np.concatenate([gray + 0.02, gray, gray - 0.02], axis=-1)  # nearly gray
    out = np.asarray(
        SaturationStretchAnalysis().run(_image(cube), QUIET).getData(), float
    )
    spread = out.max(axis=-1) - out.min(axis=-1)
    assert spread.mean() > 0.2
    assert out.min() >= 0.0 and out.max() <= 1.0
