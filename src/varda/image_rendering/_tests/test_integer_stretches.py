"""Every stretch works on whole-number images (DN products such as MISE's
int16 aggregate): results are fractions from 0 to 1, not truncated to 0."""

import numpy as np
import pytest

from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.image_rendering.image_renderer import ImageRenderer
from varda.image_rendering.stretch_algorithms import stretchAlgorithmRegistry


@pytest.mark.parametrize("dtype", [np.int16, np.uint8, np.uint32])
@pytest.mark.parametrize(
    "name",
    sorted(set(stretchAlgorithmRegistry) - {"No Stretch"}),  # raw values
)
def test_a_stretch_of_whole_numbers_spreads_from_0_to_1(name, dtype):
    image = (np.arange(400).reshape(20, 20, 1) % 200 + 10).astype(dtype)
    stretched = stretchAlgorithmRegistry[name]().apply(image)
    assert np.issubdtype(stretched.dtype, np.floating)
    assert 0 <= np.nanmin(stretched) and np.nanmax(stretched) <= 1
    assert np.nanmax(stretched) > 0.5  # not everything truncated to 0


def test_dragging_the_histogram_on_a_whole_number_image_keeps_it_visible():
    data = (np.arange(1200).reshape(20, 20, 3) % 150 + 13).astype(np.int16)
    renderer = ImageRenderer(image=VardaRaster(ArrayDataSource(data), name="dn"))
    renderer.render()
    renderer.setStretchMinMax(0, 28.0, 165.0)  # as a histogram drag does
    shown = np.asarray(renderer.render())[..., :3]
    assert shown.max() > 200
