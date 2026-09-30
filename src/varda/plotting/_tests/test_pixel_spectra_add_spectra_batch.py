"""Several spectra added as one selection survive Replace mode together."""

import numpy as np

from varda.plotting.pixel_spectra_plot import PixelSpectraPlotWidget, SpectrumMode


def test_add_spectra_batch_replaces_once(qtbot):
    widget = PixelSpectraPlotWidget()
    qtbot.addWidget(widget)
    widget.pixelConfig.mode.set(SpectrumMode.REPLACE)
    x = np.arange(10.0)
    widget.addSpectra([(x, np.ones(10), "old")])

    curves = widget.addSpectra([(x, np.full(10, 2.0), "a"), (x, np.full(10, 3.0), "b")])

    assert widget.pixelCurves == curves
    assert [c.plotDataItem.name() for c in curves] == ["a", "b"]
