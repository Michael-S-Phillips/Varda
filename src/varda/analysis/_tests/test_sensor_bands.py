"""Convolving a cube to another sensor's bands: each band a response-weighted
mean of the cube's bands, bad bands and no-data left out, bands the cube
doesn't cover skipped."""

import numpy as np
import pytest
from affine import Affine
from pyproj import CRS

from varda.analysis.registry import ANALYSES
from varda.analysis.sensor_bands import (
    SENSORS,
    SensorBandsAnalysis,
    SensorChoice,
    Sensor,
    boxcar,
    convolve,
    gaussian,
    parseBands,
    readResponses,
)
from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource

WL = np.arange(400.0, 1001.0, 5.0)  # a VNIR cube, 5 nm bands


def _cube(spectrum, shape=(4, 5)):
    return np.broadcast_to(spectrum, (*shape, WL.size)).astype(np.float64).copy()


def test_every_sensor_choice_has_its_bands():
    choices = {c.value for c in SensorChoice if c is not SensorChoice.CUSTOM}
    assert choices == set(SENSORS)


def test_a_flat_spectrum_is_the_same_in_any_band():
    values, coverage = convolve(_cube(np.full(WL.size, 0.3)), WL, SENSORS["MRO CTX"])
    assert values.shape == (4, 5, 1)
    np.testing.assert_allclose(values, 0.3)
    assert coverage == pytest.approx([1.0], abs=0.02)


def test_a_band_weights_the_spectrum_by_its_response():
    sloped = _cube(WL / 1000)
    box = Sensor("box", (boxcar("Box", 500, 800),))
    values, _ = convolve(sloped, WL, box)
    np.testing.assert_allclose(values, 0.65, atol=1e-3)  # symmetric about 650
    narrow = Sensor("narrow", (gaussian("G", 700, 40),))
    values, _ = convolve(sloped, WL, narrow)
    np.testing.assert_allclose(values, 0.70, atol=1e-3)


def test_bad_bands_and_missing_values_are_left_out():
    cube = _cube(np.full(WL.size, 0.3))
    bad = np.zeros(WL.size, bool)
    bad[WL == 650] = True
    cube[:, :, bad] = 99.0  # garbage in a bad band
    cube[0, 0, WL == 700] = np.nan  # one missing value
    values, _ = convolve(cube, WL, SENSORS["MRO CTX"], badBands=bad)
    np.testing.assert_allclose(values, 0.3)


def test_bands_the_cube_does_not_cover_are_reported_and_skipped():
    values, coverage = convolve(
        _cube(np.full(WL.size, 0.3)), WL, SENSORS["Landsat 8 OLI"]
    )
    names = [b.name for b in SENSORS["Landsat 8 OLI"].bands]
    covered = dict(zip(names, coverage))
    assert covered["B4 Red"] > 0.95 and covered["B6 SWIR 1"] == 0
    assert np.isnan(values[:, :, names.index("B6 SWIR 1")]).all()


def test_bands_typed_as_centers_and_widths_or_read_from_a_file(tmp_path):
    sensor = parseBands("Red 650/40; NIR: 860/30; 0.55/0.04")
    assert [b.name for b in sensor.bands] == ["Red", "NIR", "Band 3"]
    assert sensor.bands[2].center == pytest.approx(550, abs=1)  # µm taken as such

    path = tmp_path / "ctx_response.csv"
    grid = np.arange(0.45, 0.851, 0.01)
    response = np.where((grid >= 0.5) & (grid <= 0.8), 1.0, 0.0)
    rows = "\n".join(f"{w:.3f},{r:.2f},{r / 2:.2f}" for w, r in zip(grid, response))
    path.write_text(f"wavelength_um,CTX,Half\n{rows}\n")
    sensor = readResponses(path)
    assert [b.name for b in sensor.bands] == ["CTX", "Half"]
    assert sensor.bands[0].center == pytest.approx(650, abs=5)
    assert sensor.bands[1].response.max() == pytest.approx(1.0)  # normalized


def _image():
    spectrum = WL / 1000
    return VardaRaster(
        ArrayDataSource(
            _cube(spectrum).astype(np.float32),
            wavelengths=WL / 1000,
            wavelengthUnits="micrometers",
            transform=Affine(18, 0, 100, 0, -18, 200),
            crs=CRS.from_user_input("+proj=eqc +R=3396190 +units=m +no_defs"),
        ),
        name="crism",
    )


def test_the_analysis_makes_a_cube_in_the_sensors_bands():
    assert SensorBandsAnalysis in ANALYSES
    analysis = SensorBandsAnalysis()
    analysis.sensor.set(SensorChoice.HIRISE)
    result = analysis.run(_image(), lambda *_: None)
    assert result.bandNames == ["BG", "RED", "NIR"]
    assert result.bandModel.centers is not None
    assert result.bandModel.centers[1] == pytest.approx(700, abs=5)
    assert result.transform == Affine(18, 0, 100, 0, -18, 200)
    np.testing.assert_allclose(
        result.getBands([1])[..., 0], result.bandModel.centers[1] / 1000, atol=0.01
    )
    assert "approximate" in result.dataSource.description


def test_custom_bands_and_nothing_covered():
    analysis = SensorBandsAnalysis()
    analysis.sensor.set(SensorChoice.CUSTOM)
    analysis.custom.set("Green 550/40")
    result = analysis.run(_image(), lambda *_: None)
    assert result.bandNames == ["Green"]
    analysis.custom.set("Far 2200/100")
    with pytest.raises(ValueError, match="cover"):
        analysis.run(_image(), lambda *_: None)
    analysis.custom.set("")
    with pytest.raises(ValueError, match="Custom Bands"):
        analysis.run(_image(), lambda *_: None)


@pytest.mark.parametrize(
    "sensor, band, center",
    [
        ("Landsat 8 OLI", "B4 Red", 654.6),  # USGS: 654.6 nm
        ("Landsat 9 OLI-2", "B5 NIR", 864.6),
        ("Sentinel-2A MSI", "B4", 664.6),  # ESA: 664.6 nm
        ("Sentinel-2B MSI", "B8A", 864.0),
        ("Sentinel-2C MSI", "B11", 1610.0),
    ],
)
def test_bundled_responses_are_the_measured_ones(sensor, band, center):
    found = {b.name: b for b in SENSORS[sensor].bands}[band]
    assert found.center == pytest.approx(center, abs=2.5)
    assert "measured" in SENSORS[sensor].note and "CC-BY" in SENSORS[sensor].note


def test_ctx_follows_its_measured_passband():
    (ctx,) = SENSORS["MRO CTX"].bands
    half = ctx.wavelengths[ctx.response >= 0.5]
    # Bell et al. (2013): 50% at 515.5 and 704.7 nm, effective 611.1 nm
    assert half.min() == pytest.approx(515.5, abs=1)
    assert half.max() == pytest.approx(704.7, abs=1)
    assert ctx.center == pytest.approx(611.1, abs=3)
    onePercent = ctx.wavelengths[ctx.response >= 0.01]
    assert onePercent.min() == pytest.approx(498.2, abs=1.5)
    assert onePercent.max() == pytest.approx(754.7, abs=1.5)


def test_notes_in_a_response_file_are_skipped_and_kept(tmp_path):
    path = tmp_path / "camera.csv"
    path.write_text("# from the camera team\nwavelength_nm,Pan\n500,0\n600,1\n700,0\n")
    sensor = readResponses(path)
    assert sensor.note == "from the camera team" and sensor.bands[0].name == "Pan"
