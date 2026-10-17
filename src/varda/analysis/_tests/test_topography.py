"""Terrain from an elevation band."""

import numpy as np
import pytest
from affine import Affine
from rasterio.crs import CRS

from varda.analysis.topography import TerrainAnalysis, TerrainOutput
from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource

QUIET = lambda percent, message: None  # noqa: E731
PIXEL = 10.0  # meters


def _dtm(elevation: np.ndarray, crs=CRS.from_epsg(32612)) -> VardaRaster:
    transform = Affine(PIXEL, 0.0, 500000.0, 0.0, -PIXEL, 4000000.0)  # north up
    return VardaRaster(
        ArrayDataSource(
            elevation.astype(np.float32)[:, :, None], transform=transform, crs=crs
        ),
        name="dtm",
    )


def _run(elevation, output, image=None, **values):
    analysis = TerrainAnalysis()
    analysis.output.set(output)
    for name, value in values.items():
        analysis.params[name].set(value)
    result = analysis.run(image or _dtm(elevation), QUIET)
    return np.asarray(result.getData(), float)[:, :, 0]


ROWS, COLS = np.mgrid[0:20, 0:20].astype(float)
RISES_EAST = 2.0 * PIXEL * COLS  # 2 m up per m east
RISES_NORTH = PIXEL * (19 - ROWS)  # rows run south, so this climbs northward
INNER = (slice(2, -2), slice(2, -2))


def test_slope_of_a_plane():
    slope = _run(RISES_EAST, TerrainOutput.SLOPE)
    assert np.allclose(slope[INNER], np.degrees(np.arctan(2.0)))


@pytest.mark.parametrize(
    ("elevation", "faces"),
    [
        (RISES_EAST, 270.0),
        (-RISES_EAST, 90.0),
        (RISES_NORTH, 180.0),
        (-RISES_NORTH, 0.0),
    ],
)
def test_aspect_is_the_downhill_compass_direction(elevation, faces):
    aspect = _run(elevation, TerrainOutput.ASPECT)
    assert np.allclose(np.cos(np.radians(aspect[INNER] - faces)), 1.0)


def test_flat_ground_has_no_aspect_and_even_hillshade():
    flat = np.full((10, 10), 100.0)
    assert np.isnan(_run(flat, TerrainOutput.ASPECT)).all()
    assert np.allclose(
        _run(flat, TerrainOutput.HILLSHADE, sunElevation=45.0), np.sin(np.radians(45.0))
    )


def test_hillshade_lights_slopes_facing_the_sun():
    facing_west = _run(RISES_EAST, TerrainOutput.HILLSHADE, azimuth=270.0)
    facing_away = _run(RISES_EAST, TerrainOutput.HILLSHADE, azimuth=90.0)
    assert facing_west[INNER].mean() > facing_away[INNER].mean()


def test_curvature_of_a_hill_and_a_bowl():
    bump = -((ROWS - 10) ** 2 + (COLS - 10) ** 2) * PIXEL  # a dome
    assert _run(bump, TerrainOutput.CURVATURE)[10, 10] > 0
    assert _run(-bump, TerrainOutput.CURVATURE)[10, 10] < 0


def test_roughness_of_a_plane_is_its_mean_step():
    rough = _run(RISES_EAST, TerrainOutput.ROUGHNESS)
    # neighbors differ by 0, 20 or 20 m (3 columns each side, 2 in the middle column)
    assert np.allclose(rough[INNER], 6 * 20.0 / 8)


def test_the_z_factor_scales_elevations():
    slope = _run(RISES_EAST / 1000.0, TerrainOutput.SLOPE, zFactor=1000.0)
    assert np.allclose(slope[INNER], np.degrees(np.arctan(2.0)))


def test_an_image_without_a_projection_takes_up_as_north():
    image = VardaRaster(
        ArrayDataSource(RISES_NORTH.astype(np.float32)[:, :, None]), name="dtm"
    )
    aspect = _run(RISES_NORTH, TerrainOutput.ASPECT, image=image)
    assert np.allclose(np.cos(np.radians(aspect[INNER] - 180.0)), 1.0)


def test_degrees_per_pixel_is_refused():
    image = _dtm(np.zeros((4, 4)), crs=CRS.from_epsg(4326))
    assert "projected" in TerrainAnalysis().unavailableReason(image)


def _result(output, image, zFactor=1.0):
    analysis = TerrainAnalysis()
    analysis.output.set(output)
    analysis.zFactor.set(zFactor)
    return analysis.run(image, QUIET)


def test_an_image_without_georeferencing_says_its_slopes_are_per_pixel():
    image = VardaRaster(
        ArrayDataSource(RISES_EAST.astype(np.float32)[:, :, None]), name="dtm"
    )
    result = _result(TerrainOutput.SLOPE, image)
    assert "per pixel" in result.description
    assert "per pixel" in result.wavelengthUnits
    curvature = _result(TerrainOutput.CURVATURE, image)
    assert "pixel" in curvature.wavelengthUnits
    referenced = _result(TerrainOutput.SLOPE, _dtm(RISES_EAST))
    assert "per pixel" not in referenced.description
    assert referenced.wavelengthUnits == "degrees"


def test_roughness_units_include_the_z_factor():
    plain = _result(TerrainOutput.ROUGHNESS, _dtm(RISES_EAST))
    assert plain.wavelengthUnits == "elevation units"
    scaled = _result(TerrainOutput.ROUGHNESS, _dtm(RISES_EAST), zFactor=1000.0)
    assert scaled.wavelengthUnits == "elevation units × 1000 (Z Factor)"
