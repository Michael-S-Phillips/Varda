"""Pixel Select with a window: a region's mean spectrum with a ±1 σ band."""

import numpy as np
import pytest

from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.plotting.pixel_spectra_plot import PixelSpectraPlotWidget

WAVELENGTHS = np.array([1000.0, 1500.0, 2000.0])


def _image(cube, nodata=None) -> VardaRaster:
    return VardaRaster(
        ArrayDataSource(
            cube.astype(np.float32),
            wavelengths=WAVELENGTHS,
            wavelengthUnits="Nanometers",
            nodata=nodata,
        ),
        name="scene",
    )


@pytest.fixture
def plot(qtbot):
    widget = PixelSpectraPlotWidget()
    qtbot.addWidget(widget)
    return widget


def _cube() -> np.ndarray:
    return np.random.default_rng(0).uniform(0.1, 0.5, (10, 12, 3))


def test_a_single_pixel_is_plotted_as_before(plot):
    cube = _cube()
    (curve,) = plot.addPixelSpectra([_image(cube)], 4, 3)
    _x, y = curve.plotDataItem.getData()
    assert np.allclose(y, cube[3, 4])
    assert curve.plotDataItem.name() == "Pixel (4, 3)"
    assert curve.bandItems == []


def test_a_window_plots_the_mean_with_a_one_sigma_band(plot):
    cube = _cube()
    plot.pixelConfig.windowWidth.set(3)
    plot.pixelConfig.windowHeight.set(3)
    (curve,) = plot.addPixelSpectra([_image(cube)], 5, 4)
    window = cube[3:6, 4:7].reshape(-1, 3)
    _x, y = curve.plotDataItem.getData()
    assert np.allclose(y, window.mean(axis=0), atol=1e-6)
    upper, lower = curve.bandItems[0].getData()[1], curve.bandItems[1].getData()[1]
    assert np.allclose(upper - y, window.std(axis=0), atol=1e-5)  # population σ
    assert np.allclose(y - lower, upper - y)
    assert curve.plotDataItem.name() == "Region 3×3 at (5, 4)"
    origin = plot.pixelOrigins[curve]
    assert (origin.x, origin.y, origin.width, origin.height) == (5, 4, 3, 3)


def test_nodata_pixels_are_left_out_of_the_mean(plot):
    cube = np.full((6, 6, 3), 0.2)
    cube[2, 2] = -1.0  # no-data in the middle of the window
    plot.pixelConfig.windowWidth.set(3)
    plot.pixelConfig.windowHeight.set(3)
    (curve,) = plot.addPixelSpectra([_image(cube, nodata=-1.0)], 2, 2)
    assert np.allclose(curve.plotDataItem.getData()[1], 0.2)


def test_a_window_at_the_edge_uses_the_pixels_inside(plot):
    cube = _cube()
    plot.pixelConfig.windowWidth.set(5)
    plot.pixelConfig.windowHeight.set(5)
    (curve,) = plot.addPixelSpectra([_image(cube)], 0, 0)
    inside = cube[0:3, 0:3].reshape(-1, 3)
    assert np.allclose(curve.plotDataItem.getData()[1], inside.mean(axis=0), atol=1e-6)
