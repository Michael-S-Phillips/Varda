"""Polar stereographic maps: footprints projected and clipped, views turned
back into longitude and latitude bounds, and a graticule that fits the view."""

import numpy as np
import pytest
import shapely

from varda.workspaces.find_data.projection import (
    MapProjection,
    Projector,
    graticule,
)

NORTH = Projector(MapProjection.NORTH_POLAR, "Mars")
SOUTH = Projector(MapProjection.SOUTH_POLAR, "Mars")


def test_equirectangular_is_longitude_and_latitude():
    flat = Projector(MapProjection.EQUIRECTANGULAR, "Mars")
    box = shapely.box(10, 20, 11, 21)
    assert flat.geometry(box) is box
    assert flat.lonLatBounds((-200, -100, 30, 40)) == (-180, -90, 30, 40)


def test_the_poles_are_at_the_center_and_0e_points_away_from_the_viewer():
    x, y = NORTH.forward([0.0, 0.0, 90.0], [90.0, 80.0, 80.0])
    assert x[0] == pytest.approx(0, abs=1e-6) and y[0] == pytest.approx(0, abs=1e-6)
    assert y[1] < 0 and x[2] > 0  # 0°E down, 90°E right
    longitude, latitude = NORTH.inverse(x, y)
    assert latitude[1:] == pytest.approx([80, 80]) and longitude[2] == pytest.approx(90)
    _, y = SOUTH.forward(0.0, -80.0)
    assert y > 0  # 0°E up from the south pole


def test_a_view_around_the_pole_takes_in_every_longitude():
    r = float(np.hypot(*NORTH.forward(0.0, 70.0)))
    west, south, east, north = NORTH.lonLatBounds((-r, -r, r, r))
    assert (west, east, north) == (-180, 180, 90)
    assert south == pytest.approx(
        float(NORTH.inverse(r * np.sqrt(2), 0.0)[1])
    )  # the corners reach farthest


def test_a_view_off_the_pole_spans_its_corners():
    x, y = NORTH.forward([10.0, 30.0], [60.0, 70.0])
    view = (min(x), min(y), max(x), max(y))
    west, south, east, north = NORTH.lonLatBounds(view)
    assert -180 < west < 10 + 1e-6 and 30 - 1e-6 < east < 180
    assert south <= 60 + 1e-6 and 70 - 1e-6 <= north < 90


def test_a_view_across_180_degrees_takes_every_longitude():
    x, y = NORTH.forward([170.0, -170.0], [70.0, 75.0])
    view = (min(x), min(y), max(x), max(y))
    west, _, east, _ = NORTH.lonLatBounds(view)
    assert (west, east) == (-180, 180)


def test_footprints_are_clipped_to_the_hemisphere_and_joined_across_180():
    assert NORTH.geometry(shapely.box(0, -30, 10, -20)).is_empty
    split = shapely.MultiPolygon(
        [shapely.box(170, 80, 180, 85), shapely.box(-180, 80, -170, 85)]
    )
    joined = NORTH.geometry(split)
    assert isinstance(joined, shapely.Polygon)
    half = NORTH.geometry(shapely.box(0, -10, 10, 10))
    assert half.area == pytest.approx(NORTH.geometry(shapely.box(0, 0, 10, 10)).area)


def test_map_bounds_of_the_whole_hemisphere_are_centered_on_the_pole():
    bounds = NORTH.mapBounds(NORTH.hemisphere)
    assert bounds is not None
    x0, y0, x1, y1 = bounds
    assert x0 == pytest.approx(-x1) and y0 == pytest.approx(-y1)
    assert NORTH.mapBounds((0, -40, 10, -30)) is None


def test_the_graticule_gets_finer_as_the_view_closes_in():
    r = float(np.hypot(*NORTH.forward(0.0, 0.0)))
    wide, wideLabels = graticule(NORTH, (-r, -r, r, r))
    x, y = NORTH.forward([20.0, 22.0], [75.0, 76.0])
    close, closeLabels = graticule(NORTH, (min(x), min(y), max(x), max(y)))
    assert wide and close
    assert any(text == "60°N" for _, _, text in wideLabels)
    assert any(
        text.endswith("°N") and "." in text for _, _, text in closeLabels
    ) or any(text in ("75°N", "76°N") for _, _, text in closeLabels)
