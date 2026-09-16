"""Tests for the isolated CRISM geometry module."""

from pathlib import Path

import numpy as np

from varda.image_loading.crism_geometry import (
    ColumnGeometry,
    computeColumnLockedTranslation,
    findBandIndex,
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
    dxdy = computeColumnLockedTranslation(
        template_px, clickRow=7, clickCol=6, geometry=geom
    )
    assert dxdy is not None
    dx, dy = dxdy
    src_cx = float(template_px[:, 0].mean())  # 3.0 (vertex centroid)
    src_cy = float(template_px[:, 1].mean())  # 2.0
    # The template's mean IR sample (2.5) lies between columns 2 and 3, i.e. at
    # continuous x = 3.0 — exactly where the template already is. Locked to the
    # template's columns, not the click (6).
    assert abs((src_cx + dx) - 3.0) < 1e-6
    # dy moves the centroid to the centre of the clicked row (7 -> 7.5).
    assert abs((src_cy + dy) - 7.5) < 1e-6


def _pixelsCovered(polygon: np.ndarray, shape: tuple[int, int]) -> tuple[set, set]:
    """(rows, cols) of the pixels a (col,row) corner polygon rasterises to."""
    import rasterio.features
    from shapely.geometry import Polygon, mapping

    mask = rasterio.features.rasterize(
        [(mapping(Polygon([tuple(p) for p in polygon])), 1)],
        out_shape=shape,
        fill=0,
        dtype=np.uint8,
    ).astype(bool)
    rows, cols = np.nonzero(mask)
    return set(rows.tolist()), set(cols.tolist())


def _box(left: int, top: int, width: int, height: int) -> np.ndarray:
    return np.array(
        [
            [left, top],
            [left + width, top],
            [left + width, top + height],
            [left, top + height],
        ],
        dtype=np.float64,
    )


def test_locked_copy_of_odd_box_keeps_columns_and_centres_on_clicked_row():
    geom = _geometry()
    template = _box(left=2, top=1, width=5, height=5)  # pixels cols 2..6, rows 1..5
    dx, dy = computeColumnLockedTranslation(
        template, clickRow=7, clickCol=0, geometry=geom
    )

    rows, cols = _pixelsCovered(template + np.array([dx, dy]), geom.ir_sample.shape)
    assert cols == {2, 3, 4, 5, 6}
    assert rows == {5, 6, 7, 8, 9}  # centred on the clicked row 7


def test_locked_copy_of_even_box_keeps_columns():
    geom = _geometry()
    template = _box(left=2, top=1, width=2, height=2)  # pixels cols 2..3, rows 1..2
    dx, dy = computeColumnLockedTranslation(
        template, clickRow=7, clickCol=6, geometry=geom
    )

    rows, cols = _pixelsCovered(template + np.array([dx, dy]), geom.ir_sample.shape)
    assert cols == {2, 3}
    assert rows == {6, 7}


def test_translation_none_when_strip_absent_at_dest_row():
    geom = _geometry()
    # Make destination row 7 a different strip than the template's.
    geom.target_id[7, :] = 99
    template_px = np.array([[2, 1], [3, 1], [3, 2], [2, 2]], dtype=np.float64)
    assert (
        computeColumnLockedTranslation(
            template_px, clickRow=7, clickCol=6, geometry=geom
        )
        is None
    )


def test_translation_none_when_dest_row_out_of_bounds():
    geom = _geometry()
    template_px = np.array([[2, 1], [3, 1], [3, 2], [2, 2]], dtype=np.float64)
    assert (
        computeColumnLockedTranslation(
            template_px, clickRow=999, clickCol=6, geometry=geom
        )
        is None
    )


def test_find_band_index_matches_aliases():
    descriptions = ("IR (L-detector) Sample", "Target ID", "Segment ID (counter)")
    assert findBandIndex(descriptions, "ir_sample") == 1  # 1-indexed for rasterio
    assert findBandIndex(descriptions, "target_id") == 2
    assert findBandIndex(descriptions, "segment_id") == 3


def test_find_band_index_returns_none_when_absent():
    assert findBandIndex(("Latitude", "Longitude"), "ir_sample") is None


def test_find_band_index_prefers_ir_over_vnir_sample():
    # Real CRISM MTRDR _in geometry band order. "VNIR Sample" contains the
    # substring "ir sample", so a naive substring match wrongly picks it; the
    # IR detector sample (band 6) is the correct match for an IR cube.
    descriptions = (
        "VNIR/IR Spectral Continuity Residual",
        "VNIR/IR Spatial Gradient Residual",
        "ATM Correction Spectral Shift Artifact",
        "VNIR Sample",
        "VNIR Line",
        "IR Sample",
        "IR Line",
        "VNIR/IR Ground Sampling Offset",
        "VNIR/IR Mask",
    )
    assert findBandIndex(descriptions, "ir_sample") == 6
