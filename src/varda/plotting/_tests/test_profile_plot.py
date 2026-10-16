"""The Profiles plot: one curve per line, distance in meters or kilometers,
vertical exaggeration, the pointer's spot on the image, and CSV export."""

import csv

import numpy as np
import pytest
from affine import Affine
from pyproj import CRS

from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.lines.line_collection import LineCollection
from varda.plotting.profile_plot import ProfilePlotWidget


def _dem(pixel=20.0) -> VardaRaster:
    rows, cols = 30, 60
    heights = np.tile(np.arange(cols, dtype=np.float32) * 2.0, (rows, 1))[..., None]
    return VardaRaster(
        ArrayDataSource(
            heights,
            bandNames=["Elevation"],
            transform=Affine(pixel, 0, 0.0, 0, -pixel, 0.0),
            crs=CRS.from_user_input("+proj=eqc +R=3396190 +units=m +no_defs"),
        ),
        name="dem",
    )


@pytest.fixture
def plot(qtbot):
    widget = ProfilePlotWidget(_dem())
    qtbot.addWidget(widget)
    widget.resize(600, 400)
    widget.show()
    return widget


def _line(vertices):
    lines = LineCollection()
    lines.addLine(np.asarray(vertices, float))
    return lines.lines()


def test_a_line_becomes_a_curve_in_meters(plot):
    plot.setLines(_line([[0.5, 15], [40.5, 15]]))
    result = next(iter(plot.profiles.values()))
    assert result.distance[-1] == pytest.approx(800)  # 40 px of 20 m
    assert plot.plot.getAxis("bottom").labelText == "Distance (m)"
    assert plot.plot.getAxis("left").labelText == "Elevation"
    assert plot.verticalExaggeration() is not None
    assert "Vertical exaggeration" in plot.exaggeration.text()


def test_long_profiles_are_plotted_in_kilometers(qtbot):
    widget = ProfilePlotWidget(_dem(pixel=200.0))
    qtbot.addWidget(widget)
    widget.setLines(_line([[0.5, 15], [50.5, 15]]))  # 10 km
    assert widget.plot.getAxis("bottom").labelText == "Distance (km)"


def test_csv_has_every_sample_with_its_map_position(plot, tmp_path):
    plot.setLines(_line([[0.5, 15], [10.5, 15]]))
    plot.exportTo(tmp_path / "profile.csv")
    with open(tmp_path / "profile.csv") as f:
        rows = list(csv.reader(f))
    assert rows[0] == [
        "line",
        "distance_m",
        "x_px",
        "y_px",
        "map_x",
        "map_y",
        "Elevation",
    ]
    assert len(rows) == 12
    assert float(rows[-1][1]) == pytest.approx(200) and float(
        rows[-1][-1]
    ) == pytest.approx(20)


def test_an_image_export_writes_a_png(plot, tmp_path):
    plot.setLines(_line([[0.5, 15], [10.5, 15]]))
    plot.exportTo(tmp_path / "profile.png")
    assert (tmp_path / "profile.png").stat().st_size > 1000
