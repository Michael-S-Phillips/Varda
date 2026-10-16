"""The line collection: add, rename, recolor, remove, sessions and GIS files."""

import geopandas as gpd
import numpy as np
import pytest
from affine import Affine
from pyproj import CRS

from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.lines.line_collection import LineCollection, LineKind


def _image(georeferenced=True) -> VardaRaster:
    data = np.zeros((10, 10, 1), np.float32)
    if not georeferenced:
        return VardaRaster(ArrayDataSource(data))
    return VardaRaster(
        ArrayDataSource(
            data,
            transform=Affine(20.0, 0, 1000.0, 0, -20.0, 5000.0),
            crs=CRS.from_user_input("+proj=eqc +R=3396190 +units=m +no_defs"),
        )
    )


def test_lines_get_names_colors_and_can_change():
    lines = LineCollection()
    changes = []
    lines.sigCollectionChanged.connect(lambda: changes.append(1))
    a = lines.addLine([[0, 0], [3, 4]], LineKind.STRAIGHT)
    b = lines.addLine([[0, 0], [1, 0], [1, 1]])
    assert [line.name for line in lines.lines()] == ["Line 1", "Line 2"]
    assert lines.get(a).color != lines.get(b).color
    lines.updateLine(a, name="Crater rim", color="#ff0000")
    assert lines.get(a).name == "Crater rim" and lines.get(a).color == "#ff0000"
    lines.removeLine(b)
    assert len(lines) == 1 and len(changes) == 4
    with pytest.raises(ValueError):
        lines.addLine([[1, 1]])


def test_lengths_are_meters_when_georeferenced():
    lines = LineCollection()
    fid = lines.addLine([[0, 0], [3, 4]])
    assert lines.get(fid).length(_image()) == pytest.approx((100.0, "m"))
    assert lines.get(fid).length(_image(False)) == (5.0, "px")


def test_lines_round_trip_through_a_session():
    lines = LineCollection()
    lines.addLine([[0, 0], [3, 4]], LineKind.FREEHAND, name="Trace", color="#00ff00")
    restored = LineCollection()
    restored.addFromJson(lines.toJson())
    (line,) = restored.lines()
    assert (line.name, line.color, line.kind) == ("Trace", "#00ff00", LineKind.FREEHAND)
    np.testing.assert_allclose(line.vertices, [[0, 0], [3, 4]])


def test_lines_export_as_gis_lines_in_map_coordinates(tmp_path):
    lines = LineCollection()
    lines.addLine([[0, 0], [3, 4]], name="Profile A")
    lines.toFile(tmp_path / "lines.geojson", _image())
    frame = gpd.read_file(tmp_path / "lines.geojson")
    assert list(frame["name"]) == ["Profile A"]
    assert frame.geometry[0].coords[:] == [(1000.0, 5000.0), (1060.0, 4920.0)]
    assert frame["length"][0] == pytest.approx(100.0) and frame["units"][0] == "m"
