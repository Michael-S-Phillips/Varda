"""The 3D page's data: ground size, the decimated, quantized height grid, and
a self-contained page."""

import base64
import json
import re

import numpy as np
import pytest
from affine import Affine
from pyproj import CRS

from varda.catalogs.bodies import RADII_M, geographicCrs
from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.terrain.scene import (
    TerrainSettings,
    buildTerrain,
    fillGaps,
    groundSize,
    pageHtml,
    pngDataUrl,
    quantize,
)


def _dem(data, transform=None, crs=None, nodata=None) -> VardaRaster:
    data = np.asarray(data, np.float32)[..., None]
    if transform is None:
        return VardaRaster(ArrayDataSource(data, nodata=nodata))
    return VardaRaster(
        ArrayDataSource(
            data, transform=transform, crs=CRS.from_user_input(crs), nodata=nodata
        )
    )


def test_ground_size_in_meters_projected_geographic_or_pixels():
    projected = _dem(
        np.zeros((10, 20)), Affine(20, 0, 0, 0, -20, 0), "+proj=eqc +R=3389500 +units=m"
    )
    assert groundSize(projected) == pytest.approx((400, 200))
    geographic = _dem(
        np.zeros((10, 20)), Affine(0.01, 0, 0, 0, -0.01, 0), geographicCrs("Mars")
    )
    perDegree = np.pi * RADII_M["Mars"] / 180
    assert groundSize(geographic) == pytest.approx(
        (0.2 * perDegree, 0.1 * perDegree), rel=1e-4
    )
    assert groundSize(_dem(np.zeros((10, 20)))) == (20.0, 10.0)


def test_a_large_dem_is_averaged_down_and_no_data_becomes_nan():
    data = np.arange(100 * 60, dtype=float).reshape(100, 60)
    data[:4, :4] = -32767
    terrain = buildTerrain(_dem(data, nodata=-32767), maxSide=25)
    assert terrain.step == 4 and terrain.heights.shape == (25, 15)
    assert np.isnan(terrain.heights[0, 0])  # a block of only no data
    assert terrain.heights[1, 1] == pytest.approx(data[4:8, 4:8].mean())


def test_heights_quantize_to_16_bits_with_zero_for_no_data():
    heights = np.array([[-1500.0, np.nan], [-1000.0, -1250.0]])
    levels, low, step = quantize(heights)
    assert levels[0, 1] == 0 and levels[0, 0] == 1 and levels[1, 0] == 65535
    decoded = low + (levels.astype(float) - 1) * step
    assert decoded[1, 1] == pytest.approx(-1250, abs=step)


def test_the_page_is_self_contained_and_safe_to_inline():
    terrain = buildTerrain(_dem(np.random.default_rng(0).random((20, 30))))
    texture = pngDataUrl(np.zeros((20, 30, 4), np.uint8))
    html = pageHtml(
        terrain, texture, TerrainSettings(exaggeration=4), title="A </script> test"
    )
    assert "{{" not in html and "https://" not in html.split("Made with")[0]
    found = re.search(r'type="importmap">(.*?)</script>', html, re.S)
    assert found is not None
    importmap = json.loads(found.group(1))
    three = importmap["imports"]["three"]
    assert three.startswith("data:text/javascript;base64,")
    assert b"Three.js Authors" in base64.b64decode(three.split(",", 1)[1])[:200]
    found = re.search(r"window.VARDA_SCENE = (.*?);</script>", html, re.S)
    assert found is not None
    data = json.loads(found.group(1).replace("<\\/", "</"))
    assert (data["cols"], data["rows"]) == (30, 20) and data["settings"][
        "exaggeration"
    ] == 4
    assert data["texture"].startswith("data:image/png;base64,")
    assert 'id="panel"' not in html and "&lt;/script&gt;" in html
    assert 'id="panel"' in pageHtml(terrain, None, TerrainSettings(), panel=True)


def test_settings_ignore_keys_they_do_not_know():
    settings = TerrainSettings.fromDict({"exaggeration": 2.5, "future": 1})
    assert settings.exaggeration == 2.5 and settings.toDict()["sunAzimuth"] == 315


def test_gaps_inside_the_data_are_filled_but_the_outside_stays_empty():
    yy, xx = np.mgrid[0:30, 0:40]
    heights = (xx * 2.0).astype(np.float32)
    heights[10:14, 15:20] = np.nan  # a void on a slope
    heights[:, :3] = np.nan  # no data around the outside
    filled, count = fillGaps(heights)
    assert count == 20
    assert np.isfinite(filled[10:14, 15:20]).all() and np.isnan(filled[:, :3]).all()
    assert filled[12, 17] == pytest.approx(34, abs=3)  # follows the slope
