"""The band depth plugin finds a planted absorption and nothing elsewhere."""

import importlib.util
from pathlib import Path

import numpy as np

from varda.api import ArrayDataSource, VardaRaster

spec = importlib.util.spec_from_file_location(
    "band_depth_plugin", Path(__file__).parents[1] / "plugin.py"
)
assert spec is not None and spec.loader is not None
plugin = importlib.util.module_from_spec(spec)
spec.loader.exec_module(plugin)


def _image() -> VardaRaster:
    wavelengths = np.linspace(1700.0, 2200.0, 51)
    cube = np.full((4, 5, wavelengths.size), 0.4)
    absorbing = np.exp(-(((wavelengths - 1930.0) / 30.0) ** 2)) * 0.1
    cube[:2, :, :] -= absorbing  # the top half absorbs at 1930 nm
    source = ArrayDataSource(
        cube, wavelengths=wavelengths, wavelengthUnits="Nanometers"
    )
    return VardaRaster(source, name="synthetic")


def test_band_depth_marks_the_absorbing_pixels():
    result = plugin.BandDepth().run(_image(), lambda percent, message: None)
    depth = np.asarray(result.getBands([0]), float)[:, :, 0]
    assert np.allclose(depth[:2], 0.25, atol=0.01)  # 1 - 0.3/0.4
    assert np.allclose(depth[2:], 0.0, atol=1e-6)
    assert result.bandNames == ["BD1930"]
