"""A terrain as a closed solid: its surface, vertical sides and a flat base,
for block diagrams and 3D printing (STL). No Qt.

Every grid cell whose four corners have heights is solid: two triangles on
top, two on the base, and a wall on each side that faces an empty cell (no
data) or the edge. With smooth edges, a cell with three corners is solid
too, as the triangle between them, walled along its diagonal, and the
outline is then relaxed (each point drawn toward its neighbors along it, by
at most half a cell) so it runs smoothly rather than in 45° steps. Walls stand on every edge of
the top that no other top triangle shares, which closes the surface around
holes too, so the mesh is watertight, as printers need. Where parts of the
surface touch at a single point, each gets its own copy of it, so they share
no edge (the mesh stays manifold).
Triangles wind counterclockwise seen from outside (normals point out).
"""

from __future__ import annotations

import numpy as np
from attrs import frozen

STL_HEADER = b"Varda terrain solid"


@frozen
class Solid:
    vertices: np.ndarray  # (n, 3) float
    triangles: np.ndarray  # (m, 3) int, indices into vertices

    @property
    def facets(self) -> np.ndarray:
        """(m, 3, 3): each triangle's corners."""
        return self.vertices[self.triangles]


def solid(
    heights: np.ndarray,
    width: float,
    height: float,
    zScale: float = 1.0,
    base: float = 0.0,
    floor: float | None = None,
    smooth: bool = False,
) -> Solid:
    """``heights`` (rows, cols; NaN for no data, north row first) as a solid
    ``width`` × ``height`` across (x east, y north, centered on 0). Heights
    are multiplied by ``zScale`` about the lowest one, which sits ``base``
    above the floor (z = 0 unless ``floor`` is given, in height units);
    ``smooth`` cuts the edges diagonally."""
    heights = np.asarray(heights, float)
    rows, cols = heights.shape
    finite = np.isfinite(heights)
    low = float(np.nanmin(heights)) if finite.any() else 0.0
    z = np.where(finite, (heights - low) * zScale + base, 0.0)
    zeroAt = 0.0 if floor is None else (floor - low) * zScale + base
    x = (np.arange(cols) / max(cols - 1, 1) - 0.5) * width
    y = (0.5 - np.arange(rows) / max(rows - 1, 1)) * height
    gx, gy = np.meshgrid(x, y)
    surface = np.column_stack([gx.ravel(), gy.ravel(), z.ravel()])
    top = topTriangles(finite, smooth)
    top, copies = separateFans(top, len(surface))
    surface = np.concatenate([surface, surface[copies]])
    count = len(surface)
    # walls down from every edge of the top that no other top triangle shares
    p, q = boundaryEdges(top, count)
    if smooth:
        point = np.concatenate([np.arange(rows * cols), copies])  # on the grid
        r, c = point // cols, point % cols
        border = (r == 0) | (c == 0) | (r == rows - 1) | (c == cols - 1)
        cell = (width / max(cols - 1, 1), height / max(rows - 1, 1))
        surface[:, :2] = relaxOutline(surface[:, :2], p, q, border, cell)
    floorPoints = surface.copy()
    floorPoints[:, 2] = zeroAt
    walls = [
        np.column_stack([q, p, p + count]),
        np.column_stack([q, p + count, q + count]),
    ]
    triangles = np.concatenate([top, top[:, ::-1] + count, *walls]).astype(np.int64)
    return Solid(np.concatenate([surface, floorPoints]), triangles)


def topTriangles(finite: np.ndarray, smooth: bool) -> np.ndarray:
    """The surface's triangles (grid point indices, counterclockwise from
    above): two per cell with four corners, one per cell with three when
    ``smooth``."""
    rows, cols = finite.shape
    corners = {  # a b (north), d e (south) of every cell
        "a": finite[:-1, :-1],
        "b": finite[:-1, 1:],
        "d": finite[1:, :-1],
        "e": finite[1:, 1:],
    }
    a = np.arange(rows - 1)[:, None] * cols + np.arange(cols - 1)[None, :]
    index = {"a": a, "b": a + 1, "d": a + cols, "e": a + cols + 1}
    full = corners["a"] & corners["b"] & corners["d"] & corners["e"]
    count = sum(corner.astype(int) for corner in corners.values())
    three = (count == 3) if smooth else np.zeros_like(full)
    missing = {k: three & ~corner for k, corner in corners.items()}
    layout = {  # a triangle: where it's used
        ("a", "d", "b"): full | missing["e"],
        ("b", "d", "e"): full | missing["a"],
        ("a", "d", "e"): missing["b"],
        ("a", "e", "b"): missing["d"],
    }
    return np.concatenate(
        [
            np.column_stack([index[k][used] for k in names])
            for names, used in layout.items()
        ]
    )


def relaxOutline(
    xy: np.ndarray,
    p: np.ndarray,
    q: np.ndarray,
    pinned: np.ndarray,
    cell: tuple[float, float],
    rounds: int = 8,
) -> np.ndarray:
    """Points of an outline (edges ``p`` → ``q``, one in and one out at
    each point) moved toward the midpoint of their neighbors along it, by at
    most half a ``cell`` from where they were; ``pinned`` points stay."""
    count = len(xy)
    after, before = np.full(count, -1), np.full(count, -1)
    after[p], before[q] = q, p
    moving = p[~pinned[p] & (before[p] >= 0)]
    start, limit = xy.copy(), np.asarray(cell) / 2
    out = xy.copy()
    for _ in range(rounds):
        middle = (out[before[moving]] + out[after[moving]]) / 2
        step = out[moving] + 0.5 * (middle - out[moving])
        out[moving] = np.clip(step, start[moving] - limit, start[moving] + limit)
    return out


def boundaryEdges(triangles: np.ndarray, count: int) -> tuple[np.ndarray, np.ndarray]:
    """The directed edges (p → q, as the triangles wind) that no other
    triangle shares, as start and end indices."""
    p = triangles.ravel()
    q = np.roll(triangles, -1, axis=1).ravel()
    edges = p.astype(np.int64) * count + q
    reverse = q.astype(np.int64) * count + p
    alone = ~np.isin(edges, reverse)
    return p[alone], q[alone]


def separateFans(triangles: np.ndarray, count: int) -> tuple[np.ndarray, np.ndarray]:
    """Where separate parts of the surface meet at a single point (the
    outline passes through it twice), each part after the first gets its own
    copy of the point, so their walls share no edge. Returns the triangles
    and, per copy (indices ``count`` on), the point it copies."""
    p, _ = boundaryEdges(triangles, count)
    starts, times = np.unique(p, return_counts=True)
    shared = starts[times > 1]
    if not shared.size:
        return triangles, np.zeros(0, np.int64)
    triangles = triangles.copy()
    rowsAt: dict[int, list[int]] = {}
    for row, column in zip(*np.nonzero(np.isin(triangles, shared))):
        rowsAt.setdefault(int(triangles[row, column]), []).append(int(row))
    copies: list[int] = []
    for point, rows in rowsAt.items():
        # fans: triangles around the point joined through their other corners
        group = {row: row for row in rows}

        def find(row: int) -> int:
            while group[row] != row:
                row = group[row]
            return row

        byNeighbor: dict[int, int] = {}
        for row in rows:
            for other in triangles[row]:
                other = int(other)
                if other == point:
                    continue
                if other in byNeighbor:
                    group[find(row)] = find(byNeighbor[other])
                else:
                    byNeighbor[other] = row
        fans: dict[int, list[int]] = {}
        for row in rows:
            fans.setdefault(find(row), []).append(row)
        for fan in list(fans.values())[1:]:
            copy = count + len(copies)
            copies.append(point)
            for row in fan:
                triangles[row][triangles[row] == point] = copy
    return triangles, np.asarray(copies, np.int64)


def volume(mesh: Solid) -> float:
    """Signed volume (positive when the triangles face out)."""
    v0, v1, v2 = (mesh.facets[:, i] for i in range(3))
    return float(np.einsum("ij,ij->i", v0, np.cross(v1, v2)).sum() / 6.0)


def stlBytes(mesh: Solid) -> bytes:
    """The solid as binary STL."""
    facets = mesh.facets.astype(np.float32)
    normals = np.cross(facets[:, 1] - facets[:, 0], facets[:, 2] - facets[:, 0])
    lengths = np.linalg.norm(normals, axis=1, keepdims=True)
    normals = np.divide(normals, lengths, out=np.zeros_like(normals), where=lengths > 0)
    # each facet: its normal and three corners (12 float32), then a uint16 0
    values = np.hstack([normals, facets.reshape(-1, 9)]).astype("<f4")
    rows = np.zeros((len(facets), 50), np.uint8)
    rows[:, :48] = values.view(np.uint8).reshape(len(facets), 48)
    header = STL_HEADER.ljust(80, b" ")
    return header + np.uint32(len(facets)).tobytes() + rows.tobytes()


def printSolid(
    heights: np.ndarray,
    widthM: float,
    heightM: float,
    printWidthMm: float,
    exaggeration: float = 1.0,
    baseMm: float = 3.0,
    smooth: bool = False,
) -> Solid:
    """A solid for printing, in millimeters: ``printWidthMm`` across, heights
    at the same scale times ``exaggeration``, standing on a ``baseMm`` plinth
    below the lowest point."""
    mmPerM = printWidthMm / widthM
    return solid(
        heights,
        printWidthMm,
        heightM * mmPerM,
        zScale=mmPerM * exaggeration,
        base=baseMm,
        smooth=smooth,
    )
