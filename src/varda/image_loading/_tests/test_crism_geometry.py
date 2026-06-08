"""Tests for the isolated CRISM geometry module."""

from pathlib import Path

import numpy as np

from varda.image_loading.crism_geometry import (
    ColumnGeometry,
    computeColumnLockedTranslation,
    resolveGeometryFile,
)


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


def _geometry():
    # 10 rows x 8 cols. IR Sample = detector column index = the column number,
    # constant down each column. One strip (target 1, segment 1) everywhere.
    h, w = 10, 8
    ir = np.tile(np.arange(w, dtype=np.float64), (h, 1))
    target = np.ones((h, w), dtype=np.float64)
    segment = np.ones((h, w), dtype=np.float64)
    return ColumnGeometry(ir_sample=ir, target_id=target, segment_id=segment)


def test_translation_keeps_same_column():
    geom = _geometry()
    # 2x2 footprint over columns 2..3, rows 1..2 -> mean IR sample = 2.5.
    template_px = np.array([[2, 1], [4, 1], [4, 3], [2, 3]], dtype=np.float64)
    # Click far away at row 7, column 6. Column-lock must place the copy back on
    # the template's detector column (2 or 3), NOT at the clicked column 6.
    dxdy = computeColumnLockedTranslation(template_px, clickRow=7, clickCol=6, geometry=geom)
    assert dxdy is not None
    dx, dy = dxdy
    src_cx = float(template_px[:, 0].mean())  # 3.0 (vertex centroid)
    src_cy = float(template_px[:, 1].mean())  # 2.0
    new_col = int(round(src_cx + dx))
    assert new_col in (2, 3)  # locked to the template's column, not the click (6)
    # dy moves the centroid row to the clicked row.
    assert abs((src_cy + dy) - 7) < 1e-6


def test_translation_none_when_strip_absent_at_dest_row():
    geom = _geometry()
    # Make destination row 7 a different strip than the template's.
    geom.target_id[7, :] = 99
    template_px = np.array([[2, 1], [3, 1], [3, 2], [2, 2]], dtype=np.float64)
    assert (
        computeColumnLockedTranslation(template_px, clickRow=7, clickCol=6, geometry=geom)
        is None
    )


def test_translation_none_when_dest_row_out_of_bounds():
    geom = _geometry()
    template_px = np.array([[2, 1], [3, 1], [3, 2], [2, 2]], dtype=np.float64)
    assert (
        computeColumnLockedTranslation(template_px, clickRow=999, clickCol=6, geometry=geom)
        is None
    )
