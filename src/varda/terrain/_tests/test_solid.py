"""The terrain solid is watertight, faces out, has the right size, survives
holes, and writes valid binary STL."""

import struct
from collections import Counter

import numpy as np
import pytest

from varda.terrain.solid import blockCenters, printSolid, solid, stlBytes, volume


def _edges(mesh):
    directed = Counter()
    for tri in mesh.triangles:
        for i in range(3):
            directed[(int(tri[i]), int(tri[(i + 1) % 3]))] += 1
    return directed


def _watertight(mesh) -> bool:
    directed = _edges(mesh)
    # every edge used once in each direction: closed, consistently wound
    return all(n == 1 for n in directed.values()) and all(
        (b, a) in directed for a, b in directed
    )


def test_a_flat_plateau_is_a_closed_box_of_the_right_volume():
    heights = np.full((5, 7), 10.0)
    mesh = solid(heights, width=6.0, height=4.0, base=2.0)
    assert _watertight(mesh)
    assert volume(mesh) == pytest.approx(6 * 4 * 2)  # base only: all at the low


def test_holes_get_walls_and_the_solid_stays_closed():
    heights = np.random.default_rng(0).random((12, 15)) * 5
    heights[4:7, 5:9] = np.nan  # a hole of no data
    heights[0, 0] = np.nan
    mesh = solid(heights, 10.0, 8.0, zScale=2.0, base=1.0)
    assert _watertight(mesh)
    assert volume(mesh) > 0  # faces point out


def test_print_size_is_in_millimeters():
    yy, xx = np.mgrid[0:20, 0:30]
    heights = xx * 100.0  # 2900 m of relief across
    mesh = printSolid(heights, widthM=29000, heightM=19000, printWidthMm=150, baseMm=3)
    xs, ys, zs = mesh.vertices.T
    assert xs.max() - xs.min() == pytest.approx(150)
    assert ys.max() - ys.min() == pytest.approx(150 * 19000 / 29000)
    # 2900 m at 150 mm per 29 km is 15 mm, on a 3 mm base
    assert zs.max() == pytest.approx(3 + 15) and zs.min() == 0
    tall = printSolid(heights, 29000, 19000, 150, exaggeration=2, baseMm=3)
    assert tall.vertices[:, 2].max() == pytest.approx(3 + 30)


def test_binary_stl_has_a_header_count_and_records():
    mesh = solid(np.ones((3, 3)), 2.0, 2.0, base=1.0)
    data = stlBytes(mesh)
    (count,) = struct.unpack("<I", data[80:84])
    assert count == len(mesh.triangles) and len(data) == 84 + 50 * count
    normal = struct.unpack("<3f", data[84:96])
    assert normal == pytest.approx((0, 0, 1))  # the first triangle is on top


def test_cells_touching_only_at_a_corner_share_no_edge():
    # Two solid cells meet at a single corner, diagonally, both ways round
    for flip in (False, True):
        heights = np.full((3, 3), np.nan)
        heights[:2, :2] = 1.0
        heights[1:, 1:] = 2.0
        heights[0, 2] = heights[2, 0] = np.nan
        if flip:
            heights = heights[:, ::-1]
        mesh = solid(heights, 2.0, 2.0, base=1.0)
        assert _watertight(mesh), f"flip={flip}"


def test_smooth_edges_cut_the_staircase_diagonally():
    # data on and below the diagonal: a staircase, or with smooth edges the
    # triangle it really is (5 × 5 / 2 on 1 × 1 cells)
    rows, cols = np.mgrid[0:6, 0:6]
    heights = np.where(cols <= rows, 1.0, np.nan)
    stepped = solid(heights, 5.0, 5.0, base=1.0)
    smooth = solid(heights, 5.0, 5.0, base=1.0, smooth=True)
    assert _watertight(stepped) and _watertight(smooth)
    assert volume(stepped) == pytest.approx(10.0)
    assert volume(smooth) == pytest.approx(12.5)


@pytest.mark.parametrize("smooth", [False, True])
def test_ragged_outlines_stay_closed(smooth):
    # every kind of corner, notch, pinch and island
    for seed in range(12):
        rng = np.random.default_rng(seed)
        heights = rng.random((14, 17)) * 3
        heights[rng.random(heights.shape) < 0.3] = np.nan
        mesh = solid(heights, 10.0, 8.0, base=1.0, smooth=smooth)
        assert _watertight(mesh), f"seed={seed}"
        assert volume(mesh) > 0


def test_smooth_edges_relax_a_sawtooth_outline_into_a_line():
    # data on one side of a line at 1:2: 45° cuts alone leave a sawtooth
    rows, cols = np.mgrid[0:21, 0:41]
    heights = np.where(cols <= 2 * rows, 1.0, np.nan)
    mesh = solid(heights, 40.0, 20.0, base=1.0, smooth=True)
    assert _watertight(mesh) and volume(mesh) > 0
    top = mesh.vertices[: heights.size]
    x, y = top[:, 0] + 20, 10 - top[:, 1]  # back to columns and rows
    finite = np.isfinite(heights)
    padded = np.pad(finite, 1, constant_values=True)
    edge = finite & ~(
        padded[:-2, 1:-1] & padded[2:, 1:-1] & padded[1:-1, :-2] & padded[1:-1, 2:]
    )
    middle = edge.ravel() & (y > 3) & (y < 17)  # away from the pinned border
    offset = (x - 2 * y)[middle] / np.sqrt(5)  # across the line, in cells
    assert np.ptp(offset) < 0.05  # straight: 45° cuts alone leave 0.45


def test_block_centers_are_where_the_averaged_pixels_are():
    # 10 pixels in blocks of 4: [0, 4), [4, 8) and the partial [8, 10)
    assert blockCenters(10, 4) == pytest.approx([2 / 10, 6 / 10, 9 / 10])
    # no decimation: each pixel's center
    assert blockCenters(4, 1) == pytest.approx([0.125, 0.375, 0.625, 0.875])


def test_points_stand_at_their_block_centers():
    heights = np.ones((3, 3))
    columns, rows = blockCenters(10, 4), blockCenters(6, 2)
    mesh = solid(heights, 100.0, 60.0, columns=columns, rows=rows)
    top = mesh.vertices[: heights.size]
    assert np.unique(top[:, 0]) == pytest.approx((columns - 0.5) * 100.0)
    assert np.unique(top[:, 1]) == pytest.approx(np.sort((0.5 - rows) * 60.0))


def test_a_print_spans_its_width_between_block_centers():
    heights = np.ones((3, 3))
    columns = rows = blockCenters(10, 4)
    mesh = printSolid(heights, 1000.0, 1000.0, 140.0, columns=columns, rows=rows)
    xs, ys = mesh.vertices[:, 0], mesh.vertices[:, 1]
    assert xs.max() - xs.min() == pytest.approx(140.0)
    assert ys.max() - ys.min() == pytest.approx(140.0)  # the same scale


def test_heights_in_kilometers_print_as_tall_as_in_meters():
    _, xx = np.mgrid[0:20, 0:30]
    meters = printSolid(xx * 100.0, 29000, 19000, 150)
    kilometers = printSolid(xx * 0.1, 29000, 19000, 150, metersPerHeightUnit=1000.0)
    assert kilometers.vertices == pytest.approx(meters.vertices)


def test_the_stl_header_can_say_how_it_was_made():
    mesh = solid(np.ones((3, 3)), 2.0, 2.0, base=1.0)
    header = stlBytes(mesh, note="12 gap points filled")[:80]
    assert header.startswith(b"Varda terrain solid; 12 gap points filled")
    assert len(stlBytes(mesh, note="x" * 200)) == len(stlBytes(mesh))
    assert not stlBytes(mesh, note="x" * 200)[:80].startswith(b"solid")
