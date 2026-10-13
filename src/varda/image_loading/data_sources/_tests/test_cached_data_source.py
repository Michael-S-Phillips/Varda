"""Large images are read on demand through a small cache instead of being
loaded whole; small images still load into memory."""

import threading
import time

import numpy as np
import pytest
import spectral.io.envi as envi

from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.image_loading.data_sources.cached_data_source import CachedDataSource
from varda.image_loading.data_sources.in_memory_data_source import InMemoryDataSource
from varda.common.entities import VardaRaster
from varda.image_loading.image_loading_service import openDataSource, wrapForReading
from varda.image_rendering.image_renderer import ImageRenderer


class _CountingSource(ArrayDataSource):
    def __init__(self, data):
        super().__init__(
            data, wavelengths=np.linspace(400, 900, data.shape[2]), wavelengthUnits="nm"
        )
        self.reads = 0

    def getData(self, bandIndices=None, window=None, masked=True):
        self.reads += 1
        return super().getData(bandIndices=bandIndices, window=window, masked=masked)


@pytest.fixture
def source():
    return _CountingSource(
        np.random.default_rng(0).random((20, 30, 8)).astype(np.float32)
    )


def test_repeated_band_reads_come_from_the_cache(source):
    cached = CachedDataSource(source, maxEntries=4)
    first = cached.getBands([1, 2, 3])
    second = cached.getBands([1, 2, 3])
    assert source.reads == 1  # stored, and actually returned again
    assert second is first
    np.testing.assert_array_equal(first, source.getBands([1, 2, 3]))


def test_the_cache_keeps_only_the_most_recent_reads(source):
    cached = CachedDataSource(source, maxEntries=2)
    cached.getBands([0])
    cached.getBands([1])
    cached.getBands([0])  # refreshes [0]
    cached.getBands([2])  # evicts [1], the least recently used
    reads = source.reads
    cached.getBands([0])
    assert source.reads == reads
    cached.getBands([1])
    assert source.reads == reads + 1


def test_cached_arrays_cannot_be_changed_by_accident(source):
    data = CachedDataSource(source).getBands([0])
    with pytest.raises(ValueError):
        data[0, 0, 0] = 1.0


def test_metadata_windows_and_spectra_pass_through(source):
    cached = CachedDataSource(source)
    assert cached.bandCount == 8 and cached.width == 30 and cached.height == 20
    np.testing.assert_array_equal(cached.wavelengths, source.wavelengths)
    np.testing.assert_array_equal(
        cached.getPixelSpectrum(3, 4), source.getPixelSpectrum(3, 4)
    )
    np.testing.assert_array_equal(
        cached.getData(window=(2, 3, 4, 5)), source.getData(window=(2, 3, 4, 5))
    )


def test_small_images_load_into_memory_and_large_ones_read_on_demand(source):
    assert isinstance(wrapForReading(source, limitBytes=10**9), InMemoryDataSource)
    assert isinstance(wrapForReading(source, limitBytes=100), CachedDataSource)


def test_reads_from_several_threads_are_serialised(source):
    cached = CachedDataSource(source)
    inside = []

    class _Watching:
        def __getattr__(self, name):
            return getattr(source, name)

        def getData(self, **kwargs):
            inside.append(1)
            assert len(inside) == 1, "two reads at once"
            time.sleep(0.01)
            inside.pop()
            return source.getData(**kwargs)

    cached._source = _Watching()
    threads = [
        threading.Thread(target=cached.getData, kwargs={"window": (0, 0, 5, 5)})
        for _ in range(6)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()


def test_a_real_envi_file_read_on_demand_renders_and_gives_spectra(tmp_path, qtbot):
    cube = np.random.default_rng(1).random((25, 35, 10)).astype(np.float32)
    envi.save_image(
        str(tmp_path / "big.hdr"),
        cube,
        metadata={
            "wavelength": list(np.linspace(400, 900, 10)),
            "wavelength units": "nm",
        },
        ext=".img",
    )
    source = wrapForReading(openDataSource(str(tmp_path / "big.hdr")), limitBytes=0)
    assert isinstance(source, CachedDataSource)
    image = VardaRaster(source, name="big")
    rgba = ImageRenderer(image=image).render()
    assert rgba.shape == (25, 35, 4)
    np.testing.assert_allclose(image.getSpectrum(4, 3).values, cube[3, 4])
