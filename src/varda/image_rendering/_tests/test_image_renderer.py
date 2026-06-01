import numpy as np

from varda.common.entities import VardaRaster
from varda.image_loading.data_sources import ArrayDataSource
from varda.image_rendering.image_renderer import (
    RenderMode,
    RendererSettings,
)


def make_image(bands: int = 5) -> VardaRaster:
    data = (np.random.rand(8, 9, bands) * 100).astype(np.float32)
    wavelengths = np.array([400.0 + i * 100 for i in range(bands)])
    return VardaRaster(dataSource=ArrayDataSource(data, wavelengths=wavelengths))


def test_settings_defaults(qtbot):
    img = make_image(5)
    s = RendererSettings(img)
    assert s.image is img
    assert s.mode.get() == RenderMode.MONO
    assert s.opacity.get() == 1.0
    # bands seeded from image.defaultBands ([0, 1, 2])
    assert s.rgb.red.get() == 0
    assert s.rgb.green.get() == 1
    assert s.rgb.blue.get() == 2
    assert s.mono.band.get() == 0


def test_settings_band_params_are_image_aware(qtbot):
    img = make_image(5)
    s = RendererSettings(img)
    assert s.rgb.red.image is img
    assert s.mono.band.image is img


def test_settings_change_emits_group(qtbot):
    s = RendererSettings(make_image(5))
    received = []
    s.sigParameterChanged.connect(lambda g: received.append(g))
    s.rgb.red.set(3)
    assert received and received[-1] is s


def test_settings_stretch_default_is_auto(qtbot):
    s = RendererSettings(make_image(5))
    assert s.stretch.nameOf(s.stretch.current) == "Min-Max (Auto Full Range)"


def test_settings_defaults_single_band_image(qtbot):
    s = RendererSettings(make_image(1))
    assert s.rgb.red.get() == 0
    assert s.rgb.green.get() == 0
    assert s.rgb.blue.get() == 0
    assert s.mono.band.get() == 0
