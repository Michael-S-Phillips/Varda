"""One pixel convention everywhere: ``pixelToGeo`` gives a pixel's centre and
``geoToPixel`` the pixel containing a point, whatever the source, so derived
rasters (analysis results) line up with the image they came from."""

import numpy as np
import pytest
import rasterio
from affine import Affine
from rasterio.crs import CRS

from varda.analysis.rasters import singleBandRaster
from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.image_loading.data_sources.rasterio_data_source import RasterioDataSource

TRANSFORM = Affine(10, 0, 1000, 0, -10, 5000)  # 10 m pixels, north up


def _utm() -> CRS:
    # Built in the tests, after Varda has set up PROJ (see varda/__init__.py)
    return CRS.from_epsg(32633)


@pytest.fixture
def fileImage(tmp_path) -> VardaRaster:
    path = tmp_path / "scene.tif"
    data = np.arange(2 * 6 * 8, dtype=np.float32).reshape(2, 6, 8)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=8,
        height=6,
        count=2,
        dtype="float32",
        crs=_utm(),
        transform=TRANSFORM,
    ) as dst:
        dst.write(data)
    return VardaRaster(RasterioDataSource(str(path)), name="scene")


def test_pixel_to_geo_is_the_pixel_centre_for_every_source(fileImage):
    array = VardaRaster(
        ArrayDataSource(np.zeros((6, 8, 1)), transform=TRANSFORM, crs=_utm())
    )
    assert fileImage.pixelToGeo(3, 2) == pytest.approx((1035.0, 4975.0))
    assert array.pixelToGeo(3, 2) == pytest.approx((1035.0, 4975.0))


def test_a_derived_raster_lines_up_with_its_source(fileImage):
    derived = singleBandRaster(
        fileImage, np.zeros((6, 8)), bandName="x", name="derived"
    )
    for col, row in [(0, 0), (3, 2), (7, 5)]:
        assert derived.pixelToGeo(col, row) == pytest.approx(
            fileImage.pixelToGeo(col, row)
        )


@pytest.mark.parametrize("col, row", [(0, 0), (3, 2), (7, 5)])
def test_geo_to_pixel_inverts_pixel_to_geo(fileImage, col, row):
    derived = singleBandRaster(
        fileImage, np.zeros((6, 8)), bandName="x", name="derived"
    )
    for image in (fileImage, derived):
        assert image.geoToPixel(*image.pixelToGeo(col, row)) == (col, row)


def test_points_left_of_or_above_the_image_get_negative_pixels():
    array = VardaRaster(
        ArrayDataSource(np.zeros((6, 8, 1)), transform=TRANSFORM, crs=_utm())
    )
    assert array.geoToPixel(995.0, 5005.0) == (-1, -1)  # not truncated to 0


def test_continuous_image_coordinates_use_the_affine(fileImage):
    corners = np.array([[0.0, 0.0], [2.5, 1.25]])
    geo = fileImage.imageToGeo(corners)
    np.testing.assert_allclose(geo, [[1000, 5000], [1025, 4987.5]])
    np.testing.assert_allclose(fileImage.geoToImage(geo), corners)
