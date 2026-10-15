"""Pixels missing a few bands (bad detector columns, a no-data band) stay in
the mosaic as measured; only empty pixels let the image below show."""

import numpy as np
from affine import Affine
from rasterio.crs import CRS

from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.mosaicking.grid import defaultGrid
from varda.mosaicking.model import MosaicProject
from varda.mosaicking.radiometry import LinearMode, RadiometryMethod, balance
from varda.mosaicking.recipe import BlendMethod
from varda.mosaicking.render import NO_SOURCE, renderMosaic
from varda.mosaicking.seams import SeamMethod, computeSeams

BANDS = 10
RNG = np.random.default_rng(0)


def _image(cube, firstCol, name, nodata=None):
    source = ArrayDataSource(
        cube.astype(np.float32),
        wavelengths=np.linspace(1000, 2000, BANDS),
        wavelengthUnits="nm",
        transform=Affine(10.0, 0, firstCol * 10.0, 0, -10.0, 400.0),
        crs=CRS.from_epsg(32612),
        nodata=nodata,
    )
    return VardaRaster(source, name=name)


def _cubes():
    top = RNG.random((40, 60, BANDS)).astype(np.float32)
    top[:, 20:23, 7] = np.nan  # one band missing along three columns
    top[5:8, 30:33, :] = np.nan  # a few empty pixels
    bottom = RNG.random((40, 60, BANDS)).astype(np.float32) + 5.0
    return top, bottom


def test_a_missing_band_keeps_the_pixel():
    top, bottom = _cubes()
    project = MosaicProject([_image(top, 0, "top"), _image(bottom, 30, "bottom")])
    result = renderMosaic(project, defaultGrid(project))
    kept = result.cube[:, 20:23]
    assert np.isnan(kept[:, :, 7]).all()  # the band stays missing...
    assert np.array_equal(
        np.delete(kept, 7, axis=2), np.delete(top[:, 20:23], 7, axis=2)
    )
    assert (result.sources[:, 20:23] == 0).all()  # ...but the pixel is the top image's


def test_empty_pixels_let_the_image_below_show():
    top, bottom = _cubes()
    project = MosaicProject([_image(top, 0, "top"), _image(bottom, 30, "bottom")])
    result = renderMosaic(project, defaultGrid(project))
    assert (result.sources[5:8, 30:33] == 1).all()
    assert np.array_equal(result.cube[5:8, 30:33], bottom[5:8, 0:3])


def test_the_preview_agrees_with_the_export():
    top, bottom = _cubes()
    project = MosaicProject([_image(top, 0, "top"), _image(bottom, 30, "bottom")])
    preview = renderMosaic(project, defaultGrid(project), bands=[0, 1, 2])
    full = renderMosaic(project, defaultGrid(project))
    assert np.array_equal(preview.sources, full.sources)


def test_no_data_values_count_like_nan():
    top, bottom = _cubes()
    top = np.nan_to_num(top, nan=65535.0)
    project = MosaicProject(
        [_image(top, 0, "top", nodata=65535.0), _image(bottom, 30, "bottom")]
    )
    sources = renderMosaic(project, defaultGrid(project)).sources
    assert (sources[:, 20:23] == 0).all() and (sources[5:8, 30:33] == 1).all()


def test_a_pixel_missing_most_bands_counts_as_empty():
    top, bottom = _cubes()
    top[10, 40, :8] = np.nan  # 8 of 10 bands gone
    project = MosaicProject([_image(top, 0, "top"), _image(bottom, 30, "bottom")])
    assert renderMosaic(project, defaultGrid(project)).sources[10, 40] == 1


def test_radiometry_survives_an_empty_band():
    top, bottom = _cubes()
    top[:, :, 9] = np.nan  # a bad band, empty everywhere
    bottom = top * 1.5 + 0.1
    project = MosaicProject(
        [_image(top, 0, "top"), _image(np.roll(bottom, -30, axis=1), 30, "bottom")]
    )
    result = balance(project, RadiometryMethod.GLOBAL, LinearMode.BOTH, held={0})
    gain = result.corrections[1].gain
    assert np.allclose(gain[:9], 1 / 1.5, atol=0.02)
    assert gain[9] == 1.0  # nothing to fit: left alone


def test_seams_and_feathering_keep_partial_pixels():
    top, bottom = _cubes()
    project = MosaicProject([_image(top, 0, "top"), _image(bottom, 30, "bottom")])
    project.setSeams(SeamMethod.VORONOI, computeSeams(project, SeamMethod.VORONOI))
    project.setBlend(BlendMethod.FEATHER, width=4)
    result = renderMosaic(project, defaultGrid(project))
    assert (result.sources[:, 20:23] == 0).all()
    other = np.delete(result.cube[:, 20:23], 7, axis=2)
    assert np.isfinite(other).all() and np.allclose(
        other, np.delete(top[:, 20:23], 7, axis=2)
    )
    assert NO_SOURCE not in result.sources[:, :60]
