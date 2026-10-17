"""Spatial filters: each does what its name says on a small synthetic image."""

import numpy as np
import pytest

from varda.analysis.bandwise import BandScope
from varda.analysis.spatial_filters import (
    CustomKernelAnalysis,
    EdgeDetectionAnalysis,
    EdgeMethod,
    FilterShape,
    FrequencyFilterAnalysis,
    MorphologyAnalysis,
    MorphologyOperation,
    PassBand,
    SharpenMethod,
    SharpeningAnalysis,
    SmoothingAnalysis,
    SmoothMethod,
    SpeckleFilterAnalysis,
    SpeckleMethod,
    parseKernel,
)
from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource

QUIET = lambda percent, message: None  # noqa: E731


def _image(cube: np.ndarray, nodata=None) -> VardaRaster:
    cube = cube if cube.ndim == 3 else cube[:, :, None]
    wavelengths = np.linspace(1000.0, 2000.0, cube.shape[2])
    return VardaRaster(
        ArrayDataSource(
            cube.astype(np.float32), wavelengths=wavelengths, nodata=nodata
        ),
        name="scene",
    )


def _run(analysis, cube, **values):
    for name, value in values.items():
        analysis.params[name].set(value)
    result = analysis.run(_image(cube), QUIET)
    return np.asarray(result.getData(), float), result


def _noisy(seed=0) -> np.ndarray:
    return 0.5 + 0.1 * np.random.default_rng(seed).normal(size=(40, 40))


def _step() -> np.ndarray:
    band = np.zeros((20, 20))
    band[:, 10:] = 1.0  # a vertical edge between columns 9 and 10
    return band


@pytest.mark.parametrize("method", list(SmoothMethod))
def test_smoothing_reduces_noise_and_keeps_the_level(method):
    data, result = _run(SmoothingAnalysis(), _noisy(), method=method, size=5, sigma=1.5)
    assert data.std() < 0.7 * _noisy().std()
    assert abs(data.mean() - 0.5) < 0.02
    assert result.bandCount == 1 and result.name.startswith("scene ")


def test_median_removes_a_spike_that_mean_only_spreads():
    band = np.full((15, 15), 0.3)
    band[7, 7] = 10.0
    median, _ = _run(SmoothingAnalysis(), band, method=SmoothMethod.MEDIAN, size=3)
    mean, _ = _run(SmoothingAnalysis(), band, method=SmoothMethod.MEAN, size=3)
    assert median[:, :, 0].max() == pytest.approx(0.3)
    assert mean[7, 7, 0] > 1.0


def test_sharpening_adds_detail_and_high_pass_keeps_only_detail():
    band = _step()
    sharp, _ = _run(
        SharpeningAnalysis(), band, method=SharpenMethod.UNSHARP_MASK, amount=1.0
    )
    assert (
        sharp[:, 10, 0].mean() > 1.0 and sharp[:, 9, 0].mean() < 0.0
    )  # overshoot at the edge
    detail, _ = _run(SharpeningAnalysis(), band, method=SharpenMethod.HIGH_PASS, size=3)
    assert np.allclose(detail[:, :5, 0], 0.0) and np.allclose(detail[:, 15:, 0], 0.0)


@pytest.mark.parametrize(
    "method",
    [EdgeMethod.SOBEL, EdgeMethod.PREWITT, EdgeMethod.SCHARR, EdgeMethod.ROBERTS],
)
def test_gradient_edges_are_strongest_at_the_step(method):
    data, _ = _run(EdgeDetectionAnalysis(), _step(), method=method)
    column = data[:, :, 0].mean(axis=0)
    assert int(np.argmax(column)) in (9, 10)
    assert column[:5].max() == pytest.approx(0.0, abs=1e-9)


@pytest.mark.parametrize(
    "method",
    [EdgeMethod.SOBEL, EdgeMethod.PREWITT, EdgeMethod.SCHARR, EdgeMethod.ROBERTS],
)
@pytest.mark.parametrize("transpose", [False, True])
def test_gradient_edges_are_in_band_units_per_pixel(method, transpose):
    ramp = np.tile(np.arange(20.0) * 0.5, (20, 1))  # rises 0.5 per pixel
    ramp = ramp.T if transpose else ramp
    data, _ = _run(EdgeDetectionAnalysis(), ramp, method=method)
    assert np.allclose(data[5:-5, 5:-5, 0], 0.5)


def test_canny_marks_the_edge():
    data, _ = _run(EdgeDetectionAnalysis(), _step(), method=EdgeMethod.CANNY, sigma=1.0)
    assert set(np.unique(data)) <= {0.0, 1.0}
    assert data[5:15, 9:11, 0].any() and not data[:, :5, 0].any()


def test_directional_edges_follow_the_compass():
    rising = np.tile(np.arange(20.0), (20, 1))  # increases to the right (east)
    east, _ = _run(
        EdgeDetectionAnalysis(), rising, method=EdgeMethod.DIRECTIONAL, angle=90.0
    )
    west, _ = _run(
        EdgeDetectionAnalysis(), rising, method=EdgeMethod.DIRECTIONAL, angle=270.0
    )
    up, _ = _run(
        EdgeDetectionAnalysis(), rising, method=EdgeMethod.DIRECTIONAL, angle=0.0
    )
    assert np.allclose(east[5:-5, 5:-5, 0], 1.0)
    assert np.allclose(west[5:-5, 5:-5, 0], -1.0)
    assert np.allclose(up[5:-5, 5:-5, 0], 0.0)


def test_dilation_grows_and_opening_removes_small_features():
    band = np.zeros((21, 21))
    band[10, 10] = 1.0
    grown, _ = _run(
        MorphologyAnalysis(), band, operation=MorphologyOperation.DILATE, size=3
    )
    assert grown[:, :, 0].sum() > 1
    opened, _ = _run(
        MorphologyAnalysis(), band, operation=MorphologyOperation.OPENING, size=3
    )
    assert opened[:, :, 0].max() == 0.0
    tophat, _ = _run(
        MorphologyAnalysis(), band, operation=MorphologyOperation.WHITE_TOP_HAT, size=3
    )
    assert tophat[10, 10, 0] == 1.0


@pytest.mark.parametrize("method", list(SpeckleMethod))
def test_speckle_filters_smooth_flat_areas_and_keep_the_level(method):
    rng = np.random.default_rng(1)
    speckled = 1.0 * rng.gamma(4.0, 1 / 4.0, size=(50, 50))  # 4-look speckle, mean 1
    data, _ = _run(SpeckleFilterAnalysis(), speckled, method=method, size=7, looks=4.0)
    assert data.std() < 0.6 * speckled.std()
    assert abs(data.mean() - speckled.mean()) < 0.05


def test_frequency_filters_split_fine_and_broad_variation():
    x = np.arange(64)
    broad = np.tile(np.sin(2 * np.pi * x / 64), (64, 1))
    fine = 0.5 * np.tile(np.sin(2 * np.pi * x / 2.5), (64, 1))  # near Nyquist
    band = broad + fine
    low, _ = _run(
        FrequencyFilterAnalysis(),
        band,
        passBand=PassBand.LOW_PASS,
        shape=FilterShape.GAUSSIAN,
        cutoff=0.2,
    )
    high, _ = _run(
        FrequencyFilterAnalysis(),
        band,
        passBand=PassBand.HIGH_PASS,
        shape=FilterShape.GAUSSIAN,
        cutoff=0.2,
    )
    inner = (slice(8, -8), slice(8, -8), 0)
    assert np.abs(low[inner] - broad[8:-8, 8:-8]).max() < 0.1
    assert np.abs(high[inner] - fine[8:-8, 8:-8]).max() < 0.15


def test_band_pass_needs_the_upper_cutoff_above_the_lower():
    analysis = FrequencyFilterAnalysis()
    analysis.passBand.set(PassBand.BAND_PASS)
    analysis.cutoff.set(0.5)
    analysis.upperCutoff.set(0.3)
    assert "upper cutoff" in analysis.unavailableReason(_image(np.zeros((4, 4))))


def test_an_identity_kernel_changes_nothing():
    band = _noisy()
    data, _ = _run(CustomKernelAnalysis(), band, kernel="0 0 0; 0 1 0; 0 0 0")
    assert np.allclose(data[:, :, 0], band, atol=1e-6)


def test_a_kernel_must_be_rectangular_numbers():
    assert parseKernel("1 2\n3 4").shape == (2, 2)
    analysis = CustomKernelAnalysis()
    analysis.kernel.set("1 2 3; 4 5")
    assert "same number" in analysis.unavailableReason(_image(np.zeros((4, 4))))
    analysis.kernel.set("1 x")
    assert "isn't a number" in analysis.unavailableReason(_image(np.zeros((4, 4))))


def test_nodata_stays_nodata_and_does_not_spread():
    band = np.full((10, 10), 0.4)
    band[5, 5] = -1.0
    analysis = SmoothingAnalysis()
    analysis.method.set(SmoothMethod.MEAN)
    analysis.size.set(3)
    data = np.asarray(analysis.run(_image(band, nodata=-1.0), QUIET).getData(), float)
    assert np.isnan(data[5, 5, 0])
    assert np.allclose(data[np.isfinite(data)], 0.4)


def test_all_bands_keeps_the_bands_and_one_band_gives_one():
    cube = np.random.default_rng(2).uniform(size=(8, 9, 5))
    image = _image(cube)
    analysis = SmoothingAnalysis()
    allBands = analysis.run(image, QUIET)
    assert allBands.bandCount == 5
    np.testing.assert_array_equal(allBands.wavelengths, image.wavelengths)
    analysis.scope.set(BandScope.ONE_BAND)
    analysis.band.set(3)
    one = analysis.run(image, QUIET)
    assert one.bandCount == 1 and "band 3" in one.name
