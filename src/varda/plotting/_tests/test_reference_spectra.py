"""Adding a reference (library) spectrum to a plot with spectra already on it."""

import numpy as np

from varda.common.entities import VardaRaster
from varda.common.spectral_axis import SpectralUnit
from varda.common.vec2 import Vec2
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.plotting.pixel_spectra_plot import PixelSpectraPlotWidget
from varda.plotting.plot import RangeMode, VardaPlotWidget
from varda.utilities.debug import generate_random_image


def _spanWithin(x, y, lo, hi):
    mask = (x >= lo) & (x <= hi)
    return float(np.min(y[mask])), float(np.max(y[mask]))


def test_reference_matches_selected_curve_in_view_without_moving_the_view(qtbot):
    widget = VardaPlotWidget()
    qtbot.addWidget(widget)
    targetX = np.linspace(1000.0, 2600.0, 161)
    targetY = 0.3 + 0.1 * np.sin(targetX / 200.0)
    target = widget.plot(targetX, targetY, name="pixel")
    widget.selectPlot(target)
    widget.viewConfig.rangeMode.set(RangeMode.MANUAL)
    widget.rangeConfig.viewRangeX.set(Vec2(1500.0, 2000.0))
    widget.rangeConfig.viewRangeY.set(Vec2(0.2, 0.4))
    viewBefore = widget.viewBox.viewRange()

    # a library spectrum (nm): wider range, reflectance on a different scale
    refX = np.linspace(350.0, 2500.0, 431)
    refY = 40.0 + 15.0 * np.cos(refX / 333.0)
    curve = widget.addReferenceSpectrum("library", refX, refY)

    np.testing.assert_allclose(widget.viewBox.viewRange(), viewBefore)
    shownX, shownY = curve.displayedData()
    assert shownX.min() >= 300.0
    np.testing.assert_allclose(
        _spanWithin(shownX, shownY, 1500.0, 2000.0),
        _spanWithin(targetX, targetY, 1500.0, 2000.0),
        rtol=1e-6,
    )


def test_reference_is_plotted_as_is_when_there_is_nothing_to_match(qtbot):
    widget = VardaPlotWidget()
    qtbot.addWidget(widget)
    curve = widget.addReferenceSpectrum("library", np.arange(5.0), np.arange(5.0))

    assert curve.config.scale.value == 1.0
    assert curve.config.offset.value == 0.0


def test_pixel_plot_matches_reference_to_latest_pixel_spectrum_when_none_selected(
    qtbot,
):
    widget = PixelSpectraPlotWidget()
    qtbot.addWidget(widget)
    image = generate_random_image((20, 20, 10))
    # Odd coordinates: the Perlin test image is exactly zero on even (lattice) pixels.
    widget.addPixelSpectrum(image, 1, 1)
    latest = widget.addPixelSpectrum(image, 3, 5)
    latestX, latestY = latest.displayedData()
    assert latestY.max() > latestY.min()
    # An unpainted widget never auto-ranges, so pin the view like a user would.
    widget.viewConfig.rangeMode.set(RangeMode.MANUAL)
    widget.rangeConfig.viewRangeX.set(Vec2(2.0, 7.0))
    widget.rangeConfig.viewRangeY.set(Vec2(float(latestY.min()), float(latestY.max())))

    curve = widget.addReferenceSpectrum(
        "library", np.linspace(0.0, 9.0, 50), np.linspace(100.0, 300.0, 50)
    )

    shownX, shownY = curve.displayedData()
    np.testing.assert_allclose(
        _spanWithin(shownX, shownY, 2.0, 7.0),
        _spanWithin(latestX, latestY, 2.0, 7.0),
        rtol=1e-6,
    )
    assert curve.config.scale.value != 1.0


def test_a_library_spectrum_is_converted_to_the_unit_of_the_plotted_image(qtbot):
    widget = PixelSpectraPlotWidget()
    qtbot.addWidget(widget)
    wavelengths = np.linspace(1.0, 2.6, 10)
    data = np.random.default_rng(0).random((4, 4, 10))
    image = VardaRaster(
        ArrayDataSource(data, wavelengths=wavelengths, wavelengthUnits="Micrometers"),
        name="um image",
    )
    widget.addPixelSpectrum(image, 1, 1)
    assert widget.spectralUnit is SpectralUnit.MICROMETRE
    assert "µm" in widget.plotItem.getAxis("bottom").labelText
    curve = widget.addReferenceSpectrum(
        "library", np.linspace(1000.0, 2600.0, 50), np.ones(50)
    )
    shownX, _ = curve.displayedData()
    np.testing.assert_allclose([shownX.min(), shownX.max()], [1.0, 2.6])
