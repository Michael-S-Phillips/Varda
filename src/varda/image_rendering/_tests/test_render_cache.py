"""Changing the stretch or opacity re-uses the bands already read; only a new
band selection reads the image again. The picture is the same either way."""

import numpy as np
import pytest

from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.image_rendering.image_renderer import ImageRenderer, RenderMode


class _CountingImage(VardaRaster):
    def __init__(self, source):
        super().__init__(source, name="counted")
        self.reads = 0

    def getBands(self, bandIndices):
        self.reads += 1
        return super().getBands(bandIndices)


@pytest.fixture
def renderer():
    rng = np.random.default_rng(0)
    cube = rng.random((40, 50, 6)).astype(np.float32)
    cube[0, 0, :] = np.nan
    image = _CountingImage(ArrayDataSource(cube))
    renderer = ImageRenderer(image=image)
    renderer.settings.mode.set(RenderMode.RGB)
    renderer.render()
    return renderer, image


def _fresh(renderer: ImageRenderer) -> np.ndarray:
    """What a brand-new renderer with the same settings draws."""
    other = ImageRenderer(settings=renderer.settings)
    other.transparentNoData = renderer.transparentNoData
    return other.render()


def test_stretch_and_opacity_changes_do_not_read_the_image_again(renderer):
    renderer, image = renderer
    reads = image.reads
    renderer.setManualStretch(0.2, 0.8)
    renderer.render()
    renderer.settings.opacity.set(0.4)
    renderer.render()
    assert image.reads == reads


def test_a_new_band_selection_reads_the_image(renderer):
    renderer, image = renderer
    reads = image.reads
    renderer.settings.rgb.red.set(4)
    renderer.render()
    assert image.reads == reads + 1


def test_an_opacity_change_only_changes_the_alpha(renderer, monkeypatch):
    renderer, image = renderer
    before = renderer.render().copy()
    stretched = []
    current = renderer.settings.stretch.current
    original = current.apply
    monkeypatch.setattr(
        current, "apply", lambda data: stretched.append(1) or original(data)
    )
    renderer.settings.opacity.set(0.5)
    after = renderer.render()
    assert stretched == []
    np.testing.assert_array_equal(after[:, :, :3], before[:, :, :3])
    assert after[5, 5, 3] == int(0.5 * 255)


def test_the_cached_picture_matches_a_fresh_render(renderer):
    renderer, image = renderer
    renderer.setManualStretch(0.1, 0.7)
    renderer.settings.opacity.set(0.3)
    renderer.settings.rgb.green.set(5)
    renderer.transparentNoData = True
    renderer.settings.opacity.set(0.6)
    np.testing.assert_array_equal(renderer.render(), _fresh(renderer))
    renderer.settings.mode.set(RenderMode.MONO)
    np.testing.assert_array_equal(renderer.render(), _fresh(renderer))
