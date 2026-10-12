"""File-backed CRSs are built once, and PROJ is used from one thread at a time.

PROJ is not thread-safe: building a pyproj CRS in an analysis worker while the
GUI thread transforms coordinates for the pixel readout crashed Varda
(SIGSEGV in proj_create).
"""

import threading

import numpy as np
import rasterio
from affine import Affine

from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.rasterio_data_source import RasterioDataSource


def _geotiff(path):
    data = np.random.default_rng(0).random((3, 20, 30)).astype(np.float32)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=30,
        height=20,
        count=3,
        dtype="float32",
        crs="EPSG:32612",
        transform=Affine(30.0, 0, 500000.0, 0, -30.0, 3600000.0),
    ) as dst:
        dst.write(data)
    return str(path)


def test_crs_is_built_once_and_cached(tmp_path):
    source = RasterioDataSource(_geotiff(tmp_path / "a.tif"))
    first = source.crs
    assert first is not None and first.to_epsg() == 32612
    assert source.crs is first


def test_crs_and_lat_lon_from_many_threads(tmp_path):
    image = VardaRaster(RasterioDataSource(_geotiff(tmp_path / "b.tif")), name="b")
    errors = []

    def work():
        try:
            for i in range(200):
                assert image.crs is not None
                lat, lon = image.pixelToLatLon(i % 30, i % 20)
                assert np.isfinite(lat) and np.isfinite(lon)
        except Exception as error:  # surfaced below
            errors.append(error)

    threads = [threading.Thread(target=work) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
