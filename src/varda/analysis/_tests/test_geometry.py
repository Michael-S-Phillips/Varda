"""Resample, rotate/flip and subset keep pixels where they belong on the map."""

import numpy as np
import pytest
from affine import Affine
from rasterio.crs import CRS

from varda.analysis.geometry import (
    Interpolation,
    Orientation,
    ResampleAnalysis,
    RotateFlipAnalysis,
    SubsetAnalysis,
)
from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource

QUIET = lambda percent, message: None  # noqa: E731
TRANSFORM = Affine(18.0, 0.0, 1000.0, 0.0, -18.0, 5000.0)


def _image(rows=6, cols=9, bands=4, nodata=None, **extra) -> VardaRaster:
    cube = np.arange(rows * cols * bands, dtype=np.float32).reshape(rows, cols, bands)
    return VardaRaster(
        ArrayDataSource(
            cube,
            wavelengths=np.linspace(1000.0, 1300.0, bands),
            wavelengthUnits="Nanometers",
            transform=TRANSFORM,
            crs=CRS.from_epsg(32612),
            nodata=nodata,
            defaultBands=np.array([3, 2, 1]),
            extraMetadata=extra,
        ),
        name="scene",
    )


def _data(image: VardaRaster) -> np.ndarray:
    return np.asarray(image.getData(), float)


@pytest.mark.parametrize("how", list(Orientation))
def test_rotated_and_flipped_pixels_stay_at_their_map_position(how):
    original = _image()
    analysis = RotateFlipAnalysis()
    analysis.orientation.set(how)
    result = analysis.run(original, QUIET)
    data, source = _data(result), _data(original)
    for r in range(result.height):
        for c in range(result.width):
            x, y = result.transform * (c + 0.5, r + 0.5)
            col, row = ~original.transform * (x, y)
            assert np.array_equal(data[r, c], source[int(row), int(col)])
    if how in (Orientation.ROTATE_90_CLOCKWISE, Orientation.ROTATE_90_COUNTERCLOCKWISE):
        assert (result.height, result.width) == (original.width, original.height)


def test_resampling_halves_the_pixels_and_doubles_their_size():
    analysis = ResampleAnalysis()
    analysis.factor.set(0.5)
    result = analysis.run(_image(rows=8, cols=10), QUIET)
    assert (result.height, result.width, result.bandCount) == (4, 5, 4)
    assert result.transform.a == pytest.approx(
        36.0
    ) and result.transform.e == pytest.approx(-36.0)
    assert (result.transform.c, result.transform.f) == (1000.0, 5000.0)  # same corner


def _noise(rows=64, cols=64) -> VardaRaster:
    cube = np.random.default_rng(0).normal(size=(rows, cols, 1)).astype(np.float32)
    return VardaRaster(ArrayDataSource(cube, transform=TRANSFORM), name="noise")


@pytest.mark.parametrize("how", [Interpolation.BILINEAR, Interpolation.CUBIC])
def test_shrinking_with_interpolation_averages_away_fine_detail(how):
    """Anti-aliased as scikit-image's resize: a Gaussian of σ = (1/factor −
    1) / 2 old pixels first, so pixel-scale noise averages down."""
    analysis = ResampleAnalysis()
    analysis.factor.set(0.25)
    analysis.interpolation.set(how)
    data = _data(analysis.run(_noise(), QUIET))
    assert data.std() < 0.25


def test_shrinking_with_nearest_neighbor_keeps_the_values():
    analysis = ResampleAnalysis()
    analysis.factor.set(0.25)
    analysis.interpolation.set(Interpolation.NEAREST)
    original = _noise()
    data = _data(analysis.run(original, QUIET))
    assert np.isin(data, _data(original)).all()


def test_the_description_records_the_actual_factors():
    analysis = ResampleAnalysis()
    analysis.factor.set(0.5)
    result = analysis.run(_image(rows=5, cols=7, bands=1), QUIET)
    assert (result.height, result.width) == (2, 4)  # rounded pixel counts
    assert "rows ×0.4" in result.description
    assert "columns ×0.571429" in result.description


def test_nearest_neighbor_enlarging_repeats_values():
    analysis = ResampleAnalysis()
    analysis.factor.set(2.0)
    analysis.interpolation.set(Interpolation.NEAREST)
    original = _image(rows=3, cols=3, bands=1)
    data = _data(analysis.run(original, QUIET))[:, :, 0]
    assert np.array_equal(data[::2, ::2], _data(original)[:, :, 0])
    assert np.array_equal(data[1::2, 1::2], _data(original)[:, :, 0])


def test_resampling_keeps_nodata_as_nodata():
    original = _image(rows=4, cols=4, bands=1, nodata=5.0)  # pixel (1, 1) holds 5
    analysis = ResampleAnalysis()
    analysis.factor.set(2.0)
    analysis.interpolation.set(Interpolation.NEAREST)
    data = _data(analysis.run(original, QUIET))[:, :, 0]
    assert np.isnan(data[2:4, 2:4]).all() and np.isfinite(data[:2, :2]).all()


def test_a_subset_crops_and_keeps_band_metadata():
    original = _image(
        fwhm="{ 10, 11, 12, 13 }", bbl=[1, 0, 1, 1], reflectance_scale_factor=10000
    )
    analysis = SubsetAnalysis()
    analysis.prepareFor(original)
    assert (analysis.lastRow.value, analysis.lastColumn.value) == (6, 9)
    analysis.firstRow.set(2)
    analysis.lastRow.set(4)
    analysis.firstColumn.set(3)
    analysis.lastColumn.set(5)
    analysis.bands.set("2-4")
    result = analysis.run(original, QUIET)
    assert (result.height, result.width, result.bandCount) == (3, 3, 3)
    assert np.array_equal(_data(result), _data(original)[1:4, 2:5, 1:4])
    np.testing.assert_allclose(result.wavelengths, [1100.0, 1200.0, 1300.0])
    assert result.extraMetadata["fwhm"] == [11.0, 12.0, 13.0]
    assert result.extraMetadata["bbl"] == [0.0, 1.0, 1.0]
    assert result.extraMetadata["reflectance_scale_factor"] == 10000
    assert result.transform * (0, 0) == original.transform * (
        2,
        1,
    )  # top-left corner moved
    assert list(result.defaultBands) == [2, 1, 0]


def test_a_subset_outside_the_image_is_refused():
    original = _image()
    analysis = SubsetAnalysis()
    analysis.prepareFor(original)
    analysis.lastRow.set(99)
    assert "Rows" in analysis.unavailableReason(original)
    analysis.lastRow.set(6)
    analysis.bands.set("50-60")
    assert "No bands" in analysis.unavailableReason(original)
