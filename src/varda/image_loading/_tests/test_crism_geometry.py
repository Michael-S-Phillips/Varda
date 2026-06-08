"""Tests for the isolated CRISM geometry module."""

from pathlib import Path

from varda.image_loading.crism_geometry import resolveGeometryFile


def _touch(p: Path) -> None:
    p.write_bytes(b"")


def test_resolves_per_strip_mtrdr(tmp_path):
    src = tmp_path / "frt00013000_07_if166j_mtr3.img"
    _touch(src)
    ddr = tmp_path / "frt00013000_07_in166j_mtr3.img"
    _touch(ddr)
    assert resolveGeometryFile(str(src)) == str(ddr)


def test_resolves_mosaic_tile(tmp_path):
    src = tmp_path / "t0886_mrral_05s058_0327_4.img"
    _touch(src)
    ddr = tmp_path / "t0886_mrrde_05s058_0327_4.img"
    _touch(ddr)
    assert resolveGeometryFile(str(src)) == str(ddr)


def test_returns_none_when_companion_missing(tmp_path):
    src = tmp_path / "frt00013000_07_if166j_mtr3.img"
    _touch(src)
    assert resolveGeometryFile(str(src)) is None


def test_returns_none_for_non_crism_name(tmp_path):
    src = tmp_path / "some_geotiff.tif"
    _touch(src)
    assert resolveGeometryFile(str(src)) is None
