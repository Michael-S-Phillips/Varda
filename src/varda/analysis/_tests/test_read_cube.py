"""Analyses read cubes through readCube: nodata becomes NaN, a pixel's few
missing bands are filled along its spectrum, and only pixels missing most of
their bands are dropped — instead of dropping every pixel with any bad band."""

import numpy as np

from varda.analysis.rasters import fillAlongSpectrum, readCube
from varda.analysis.transforms import PcaAnalysis
from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource


def test_a_missing_band_is_interpolated_from_its_neighbours():
    cube = np.tile(np.arange(6.0), (2, 2, 1))  # spectrum 0,1,2,3,4,5 everywhere
    cube[0, 0, 2] = np.nan
    cube[1, 1, 3] = np.nan

    filled, valid = fillAlongSpectrum(cube)

    assert valid.all()
    assert filled[0, 0, 2] == 2.0 and filled[1, 1, 3] == 3.0
    np.testing.assert_array_equal(filled[0, 1], np.arange(6.0))  # untouched


def test_a_gap_of_several_bands_is_filled_linearly():
    cube = np.tile(np.array([0.0, 1.0, 2.0, 3.0, 4.0, 5.0]), (1, 1, 1))
    cube[0, 0, 1:4] = np.nan  # 0, -, -, -, 4, 5

    filled, _ = fillAlongSpectrum(cube)

    np.testing.assert_allclose(filled[0, 0], [0.0, 1.0, 2.0, 3.0, 4.0, 5.0])


def test_missing_end_bands_take_the_nearest_value():
    cube = np.array([[[np.nan, 1.0, 2.0, 3.0, np.nan]]])

    filled, valid = fillAlongSpectrum(cube)

    assert valid.all()
    np.testing.assert_array_equal(filled[0, 0], [1.0, 1.0, 2.0, 3.0, 3.0])


def test_pixels_missing_most_bands_are_invalid_and_left_nan():
    cube = np.tile(np.arange(6.0), (1, 3, 1))
    cube[0, 0, :] = np.nan  # nothing at all
    cube[0, 1, :4] = np.nan  # more than half missing
    cube[0, 2, :2] = np.nan  # a third missing: still a usable spectrum

    filled, valid = fillAlongSpectrum(cube)

    assert list(valid[0]) == [False, False, True]
    assert np.isnan(filled[0, 0]).all() and np.isnan(filled[0, 1]).all()
    assert np.isfinite(filled[0, 2]).all()


def test_read_cube_treats_nodata_as_missing_and_returns_float64():
    cube = np.tile(np.arange(6.0), (2, 2, 1)).astype(np.float32)
    cube[0, 0, 2] = -9999.0
    cube[1, 1, :] = -9999.0
    image = VardaRaster(ArrayDataSource(cube, nodata=-9999.0), name="scene")

    filled, valid = readCube(image)

    assert filled.dtype == np.float64
    assert filled[0, 0, 2] == 2.0
    assert list(valid.ravel()) == [True, True, True, False]
    assert np.isnan(filled[1, 1]).all()


def test_transforms_keep_pixels_that_merely_have_a_bad_band():
    rng = np.random.default_rng(0)
    cube = rng.random((10, 10, 6))
    cube[:5, :, 3] = -9999.0  # one band missing over half the image
    cube[0, 0, :] = -9999.0  # one pixel missing entirely
    image = VardaRaster(ArrayDataSource(cube, nodata=-9999.0), name="scene")
    analysis = PcaAnalysis()
    analysis.components.set(3)

    result = analysis.run(image, lambda p, m: None)

    data = result.getData()
    assert np.isnan(data[0, 0]).all()
    assert np.isfinite(data[5:]).all()
    assert np.isfinite(data[:5, 1:]).all()  # kept despite the bad band
