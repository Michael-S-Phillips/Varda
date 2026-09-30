"""Any spectrum (not just a pixel's) can join the pixel plot under its rules."""

import numpy as np

from varda.plotting.pixel_spectra_plot import (
    ColorScheme,
    PixelSpectraPlotWidget,
    SpectrumMode,
    paletteColor,
)


def test_add_spectrum_uses_the_palette_and_is_tracked_like_a_pixel_curve(qtbot):
    widget = PixelSpectraPlotWidget()
    qtbot.addWidget(widget)

    curve = widget.addSpectrum(np.arange(10.0), np.linspace(0.5, 1.5, 10), "Ratio A")

    assert widget.pixelCurves == [curve]
    assert curve.plotDataItem.name() == "Ratio A"
    assert curve.config.color.value == paletteColor(ColorScheme.TAB10, 0).toQColor()


def test_add_spectrum_honours_replace_mode(qtbot):
    widget = PixelSpectraPlotWidget()
    qtbot.addWidget(widget)
    widget.pixelConfig.mode.set(SpectrumMode.REPLACE)
    widget.addSpectrum(np.arange(10.0), np.ones(10), "first")
    second = widget.addSpectrum(np.arange(10.0), np.full(10, 2.0), "second")

    assert widget.pixelCurves == [second]
