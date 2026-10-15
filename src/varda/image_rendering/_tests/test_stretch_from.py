"""The stretch and the histogram can take their statistics from the whole
image or from what the main or zoom view shows, and the stretch then applies
to the whole image."""

import numpy as np
import pytest

from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.image_rendering.image_renderer import ImageRenderer, StretchSource
from varda.image_rendering.new_histogram_view import NewHistogramView
from varda.image_rendering.stretch_algorithms import (
    HistogramEqualizationStretch,
    LinearPercentileStretch,
    MinMaxStretch,
)

DARK = (slice(0, 10), slice(0, 10))  # values 0-1; the rest of the image is 0-100


def _image() -> np.ndarray:
    data = np.random.default_rng(0).random((40, 40, 1)) * 100
    data[DARK] = np.random.default_rng(1).random((10, 10, 1))
    return data


@pytest.mark.parametrize(
    "stretch", [MinMaxStretch, LinearPercentileStretch, HistogramEqualizationStretch]
)
def test_statistics_come_from_the_sample_and_apply_to_the_whole_image(stretch):
    image = _image()
    out = stretch().apply(image, image[DARK])
    assert out[DARK].max() > 0.9  # the dark corner fills the range
    assert np.median(out[10:, 10:]) == pytest.approx(1.0)  # brighter is clipped
    whole = stretch().apply(image)
    assert whole[DARK].max() < 0.1


def _renderer() -> ImageRenderer:
    return ImageRenderer(image=VardaRaster(ArrayDataSource(_image().astype("f4"))))


def test_the_renderer_stretches_from_the_chosen_view(qtbot):
    renderer = _renderer()
    renderer.setStretchWindow(StretchSource.ZOOM, DARK)
    full = float(np.ravel(renderer.getMinMaxValues()[1])[0])
    assert full > 90  # Full image is the default
    with qtbot.waitSignal(renderer.sigShouldRefresh):
        renderer.settings.stretchFrom.set(StretchSource.ZOOM)
    assert float(np.ravel(renderer.getMinMaxValues()[1])[0]) < 1.0
    assert renderer.getSampleData().shape[:2] == (10, 10)


def test_a_window_that_jitters_by_a_pixel_keeps_the_stretch(qtbot):
    renderer = _renderer()
    renderer.settings.stretchFrom.set(StretchSource.MAIN)
    renderer.setStretchWindow(StretchSource.MAIN, DARK)
    sample = renderer.getSampleData()
    with qtbot.assertNotEmitted(renderer.sigShouldRefresh):
        renderer.setStretchWindow(StretchSource.MAIN, (slice(1, 10), slice(0, 11)))
        renderer.setStretchWindow(StretchSource.ZOOM, (slice(20, 30), slice(20, 30)))
    assert renderer.getSampleData() is sample  # the histogram keeps its zoom


def test_a_view_of_only_no_data_falls_back_to_the_whole_image():
    data = _image().astype("f4")
    data[DARK] = np.nan
    renderer = ImageRenderer(image=VardaRaster(ArrayDataSource(data)))
    renderer.settings.stretchFrom.set(StretchSource.ZOOM)
    renderer.setStretchWindow(StretchSource.ZOOM, DARK)
    assert renderer.getSampleData().shape[:2] == (40, 40)


def test_the_histogram_shows_the_sample(qtbot):
    renderer = _renderer()
    view = NewHistogramView(renderer)
    qtbot.addWidget(view)
    renderer.setStretchWindow(StretchSource.ZOOM, DARK)
    renderer.settings.stretchFrom.set(StretchSource.ZOOM)
    values = view._values[view.monoPlot]
    assert values.size == 100 and values.max() < 1.0
