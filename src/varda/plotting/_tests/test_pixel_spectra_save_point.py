"""The pixel-spectra plot can ask for its pixels to be saved as points."""

from varda.plotting.pixel_spectra_plot import PixelSpectraPlotWidget
from varda.utilities.debug import generate_random_image


def test_save_point_asks_for_the_selected_pixel_curve(qtbot):
    plot = PixelSpectraPlotWidget()
    qtbot.addWidget(plot)
    image = generate_random_image((20, 20, 10))
    (first,) = plot.addPixelSpectra([image], 3, 5)
    (second,) = plot.addPixelSpectra([image], 7, 9)
    requests = []
    plot.sigSavePointRequested.connect(requests.append)

    plot.savePointButton.click()  # nothing selected: the latest pixel spectrum
    plot.selectPlot(first)
    plot.savePointButton.click()

    assert requests == [second, first]


def test_save_all_points_asks_for_every_pixel_curve(qtbot):
    plot = PixelSpectraPlotWidget()
    qtbot.addWidget(plot)
    image = generate_random_image((20, 20, 10))
    curves = plot.addPixelSpectra([image], 3, 5) + plot.addPixelSpectra([image], 7, 9)
    plot.addSpectrum([1.0, 2.0], [0.5, 0.6], "not a pixel")  # has no origin
    requests = []
    plot.sigSavePointRequested.connect(requests.append)

    plot.saveAllPointsButton.click()

    assert requests == curves


def test_save_buttons_are_disabled_without_pixel_spectra(qtbot):
    plot = PixelSpectraPlotWidget()
    qtbot.addWidget(plot)
    assert not plot.savePointButton.isEnabled()

    image = generate_random_image((20, 20, 10))
    plot.addPixelSpectra([image], 3, 5)
    assert plot.savePointButton.isEnabled()

    plot.clearPixelSpectra()
    assert not plot.savePointButton.isEnabled()
