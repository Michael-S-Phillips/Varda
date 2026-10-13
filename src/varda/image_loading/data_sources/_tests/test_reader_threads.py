"""A rasterio file handle is never shared between threads: the display and a
background analysis each read through their own."""

import threading

import numpy as np
import rasterio
from rasterio.transform import from_origin

from varda.image_loading.data_sources.rasterio_data_source import RasterioDataSource


def _writeTiff(path, data):
    bands, height, width = data.shape
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        width=width,
        height=height,
        count=bands,
        dtype=data.dtype,
        transform=from_origin(0, 0, 1, 1),
    ) as dst:
        dst.write(data)


def _inThread(function):
    result = []
    thread = threading.Thread(target=lambda: result.append(function()))
    thread.start()
    thread.join()
    return result[0]


def test_each_thread_reads_through_its_own_handle(tmp_path):
    data = np.arange(3 * 8 * 8, dtype=np.float32).reshape(3, 8, 8)
    _writeTiff(tmp_path / "a.tif", data)
    source = RasterioDataSource(str(tmp_path / "a.tif"))
    mainHandle = source._reader()
    workerHandle = _inThread(source._reader)
    assert workerHandle is not mainHandle
    assert source._reader() is mainHandle  # reused within a thread
    source.close()
    assert mainHandle.closed and workerHandle.closed


def test_concurrent_reads_return_the_right_data(tmp_path):
    data = np.random.default_rng(0).random((20, 64, 64)).astype(np.float32)
    _writeTiff(tmp_path / "a.tif", data)
    source = RasterioDataSource(str(tmp_path / "a.tif"))
    expected = np.moveaxis(data, 0, -1)
    errors = []

    def read(band: int) -> None:
        for _ in range(20):
            got = source.getData(bandIndices=[band])
            if not np.array_equal(got[..., 0], expected[..., band]):
                errors.append(band)

    threads = [threading.Thread(target=read, args=(b,)) for b in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    source.close()
    assert errors == []
