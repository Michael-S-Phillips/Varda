import numpy as np

from varda.common.entities import VardaRaster
from varda.image_loading.data_sources import ArrayDataSource
from varda.image_rendering.render_parameters import BandParameter


def make_image(bands: int = 5) -> VardaRaster:
    data = (np.random.rand(8, 9, bands) * 100).astype(np.float32)
    wavelengths = np.array([400.0 + i * 100 for i in range(bands)])
    return VardaRaster(dataSource=ArrayDataSource(data, wavelengths=wavelengths))


def test_band_parameter_set_get(qtbot):
    p = BandParameter("Band", 0)
    p.setImage(make_image(5))
    p.set(3)
    assert p.get() == 3


def test_band_parameter_clamps_stale_value_on_set_image(qtbot):
    p = BandParameter("Band", 0)
    p.value = 99  # stale index from before an image was attached
    p.setImage(make_image(5))
    assert p.get() == 0


def test_band_parameter_clone_preserves_value_and_image(qtbot):
    img = make_image(5)
    p = BandParameter("Band", 0)
    p.setImage(img)
    p.set(2)
    c = p.clone()
    assert c.get() == 2
    assert c.image is img


def test_band_parameter_widget_reflects_value(qtbot):
    img = make_image(4)
    p = BandParameter("Band", 0)
    p.setImage(img)
    w = p.getWidget()
    qtbot.addWidget(w)
    p.set(2)
    assert w.comboBox.currentIndex() == 2
