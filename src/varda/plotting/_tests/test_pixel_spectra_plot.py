"""Tests for the persistent pixel-spectra plot (collect/replace, palettes, clear)."""

import numpy as np
import pytest

from varda.common.vec2 import Vec2
from varda.plotting.pixel_spectra_plot import (
    ColorScheme,
    PixelSpectraPlotWidget,
    SpectrumMode,
    paletteColor,
)
from varda.utilities.debug import generate_random_image


@pytest.fixture
def image():
    return generate_random_image((20, 20, 10))


@pytest.fixture
def widget(qtbot):
    widget = PixelSpectraPlotWidget()
    qtbot.addWidget(widget)
    return widget


def _color(scheme: ColorScheme, index: int):
    return paletteColor(scheme, index).toQColor()


def test_collect_mode_accumulates_spectra_with_successive_palette_colors(widget, image):
    widget.addPixelSpectrum(image, 1, 1)
    widget.addPixelSpectrum(image, 2, 2)

    assert len(widget.pixelCurves) == 2
    assert all(curve in widget.plots for curve in widget.pixelCurves)
    colors = [curve.config.color.value for curve in widget.pixelCurves]
    assert colors == [_color(ColorScheme.TAB10, 0), _color(ColorScheme.TAB10, 1)]


def test_replace_mode_keeps_only_latest_spectrum(widget, image):
    widget.pixelConfig.mode.set(SpectrumMode.REPLACE)
    widget.addPixelSpectrum(image, 1, 1)
    widget.addPixelSpectrum(image, 2, 2)

    assert len(widget.pixelCurves) == 1
    assert len(widget.plots) == 1
    _x, y = widget.pixelCurves[0].plotDataItem.getData()
    np.testing.assert_array_equal(y, image.getSpectrum(2, 2).values)


def test_replace_mode_preserves_non_pixel_curves(widget, image):
    library = widget.plot(np.arange(10.0), np.linspace(0.0, 1.0, 10), name="library")
    widget.pixelConfig.mode.set(SpectrumMode.REPLACE)
    widget.addPixelSpectrum(image, 1, 1)
    widget.addPixelSpectrum(image, 2, 2)

    assert library in widget.plots
    assert len(widget.plots) == 2


def test_clear_removes_pixel_spectra_and_restarts_palette(widget, image):
    widget.addPixelSpectrum(image, 1, 1)
    widget.addPixelSpectrum(image, 2, 2)
    widget.clearPixelSpectra()
    assert widget.pixelCurves == []
    assert widget.plots == []

    curve = widget.addPixelSpectrum(image, 3, 3)
    assert curve.config.color.value == _color(ColorScheme.TAB10, 0)


def test_color_scheme_change_applies_to_next_spectrum(widget, image):
    widget.addPixelSpectrum(image, 1, 1)
    widget.pixelConfig.colorScheme.set(ColorScheme.SET1)
    curve = widget.addPixelSpectrum(image, 2, 2)

    assert curve.config.color.value == _color(ColorScheme.SET1, 1)


def test_removing_pixel_curve_via_plot_keeps_tracking_in_sync(widget, image):
    first = widget.addPixelSpectrum(image, 1, 1)
    widget.addPixelSpectrum(image, 2, 2)
    widget.removePlot(first)

    assert len(widget.pixelCurves) == 1
    assert first not in widget.pixelCurves


def test_out_of_bounds_pixel_is_ignored(widget, image):
    assert widget.addPixelSpectrum(image, image.width, 0) is None
    assert widget.addPixelSpectrum(image, 0, -1) is None
    assert widget.pixelCurves == []


def test_manual_view_range_persists_when_spectrum_added(widget, image):
    widget.addPixelSpectrum(image, 1, 1)
    values = image.getSpectrum(1, 1).values
    yLow, yHigh = np.percentile(values, [25, 75])
    widget.windowConfig.autoViewRange.set(False)
    widget.rangeConfig.viewRangeX.set(Vec2(2.0, 6.0))
    widget.rangeConfig.viewRangeY.set(Vec2(float(yLow), float(yHigh)))
    before = widget.viewBox.viewRange()

    widget.addPixelSpectrum(image, 3, 3)

    after = widget.viewBox.viewRange()
    np.testing.assert_allclose(after, before)
