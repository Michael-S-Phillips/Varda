"""Bodies: names, geographic coordinate systems, longitude conventions."""

import pytest
from rasterio.crs import CRS

from varda.catalogs.bodies import bodyName, geographicCrs, normalizeLongitude


def test_names_are_normalized():
    assert bodyName("mars") == bodyName("MARS") == "Mars"
    assert bodyName(" europa ") == "Europa"


def test_each_body_has_a_geographic_crs():
    assert geographicCrs("Earth") == "EPSG:4326"
    mars = CRS.from_user_input(geographicCrs("mars"))
    assert mars.is_geographic
    with pytest.raises(ValueError, match="size"):
        geographicCrs("Arrokoth")


@pytest.mark.parametrize(
    ("raw", "expected"), [(0, 0), (77.5, 77.5), (282.5, -77.5), (360, 0), (-190, 170)]
)
def test_longitudes_run_from_minus_180_to_180(raw, expected):
    assert normalizeLongitude(raw) == pytest.approx(expected)
