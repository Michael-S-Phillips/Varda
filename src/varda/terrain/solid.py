"""A terrain as a closed solid: its surface, vertical sides and a flat base,
for block diagrams and 3D printing (STL). No Qt.

Every grid cell whose four corners have heights is solid: two triangles on
top, two on the base, and a wall on each side that faces an empty cell (no
data) or the edge. That closes the surface around holes too, so the mesh is
watertight, as printers need. Where two solid cells touch only at a corner,
diagonally, the southern one gets its own copy of that corner, so the two
parts share no edge (the mesh stays manifold). Triangles wind
counterclockwise seen from outside (normals point out).
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
) -> Solid:
    """``heights`` (rows, cols; NaN for no data, north row first) as a solid
    ``width`` × ``height`` across (x east, y north, centered on 0). Heights
    are multiplied by ``zScale`` about the lowest one, which sits ``base``
    above the floor (z = 0 unless ``floor`` is given, in height units)."""
    heights = np.asarray(heights, float)
    rows, cols = heights.shape
    finite = np.isfinite(heights)
    low = float(np.nanmin(heights)) if finite.any() else 0.0
    top = np.where(finite, (heights - low) * zScale + base, 0.0)
    zeroAt = 0.0 if floor is None else (floor - low) * zScale + base
    x = (np.arange(cols) / max(cols - 1, 1) - 0.5) * width
    y = (0.5 - np.arange(rows) / max(rows - 1, 1)) * height
    gx, gy = np.meshgrid(x, y)
    n = rows * cols
    vertices = np.concatenate(
        [
            np.column_stack([gx.ravel(), gy.ravel(), top.ravel()]),
            np.column_stack([gx.ravel(), gy.ravel(), np.full(n, zeroAt)]),
        ]
    )
    # cells with all four corners
    valid = finite[:-1, :-1] & finite[:-1, 1:] & finite[1:, :-1] & finite[1:, 1:]
    r, c = np.nonzero(valid)
    a = r * cols + c  # corners: a b (north), d e (south)
    b, d = a + 1, a + cols
    e = d + 1
    padded = np.pad(valid, 1, constant_values=False)
    # Pinch points: a grid point whose four cells are solid only diagonally
    nw, ne = padded[:-1, :-1], padded[:-1, 1:]
    sw, se = padded[1:, :-1], padded[1:, 1:]
    pinchSE = nw & se & ~ne & ~sw  # the SE cell's a corner is shared
    pinchSW = ne & sw & ~nw & ~se  # the SW cell's b corner is shared
    copies: list[np.ndarray] = []

    def ownCopy(
        corner: np.ndarray, pinched: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        """``corner``'s top and base vertex indices, with the pinched cells'
        moved to new copies (appended after the 2n grid vertices)."""
        top, base = corner.copy(), corner + n
        cells = np.flatnonzero(pinched)
        if cells.size:
            start = 2 * n + sum(len(x) for x in copies)
            copies.extend([vertices[corner[cells]], vertices[corner[cells] + n]])
            top[cells] = start + np.arange(cells.size)
            base[cells] = start + cells.size + np.arange(cells.size)
        return top, base

    aTop, aBase = ownCopy(a, pinchSE[r, c])
    bTop, bBase = ownCopy(b, pinchSW[r, c + 1])
    corners = {"a": (aTop, aBase), "b": (bTop, bBase), "d": (d, d + n), "e": (e, e + n)}
    (aT, aB), (bT, bB), (dT, dB), (eT, eB) = corners.values()
    pieces = [
        np.column_stack([aT, dT, bT]),  # top
        np.column_stack([bT, dT, eT]),
        np.column_stack([aB, bB, dB]),  # base, facing down
        np.column_stack([bB, eB, dB]),
    ]
    sides = {  # (neighbor offset, first corner, second corner)
        "north": ((-1, 0), "a", "b"),
        "south": ((1, 0), "e", "d"),
        "west": ((0, -1), "d", "a"),
        "east": ((0, 1), "b", "e"),
    }
    for (dr, dc), first, second in sides.values():
        open_ = ~padded[r + 1 + dr, c + 1 + dc]
        (pT, pB), (qT, qB) = corners[first], corners[second]
        pT, pB, qT, qB = pT[open_], pB[open_], qT[open_], qB[open_]
        pieces.append(np.column_stack([pT, qT, qB]))
        pieces.append(np.column_stack([pT, qB, pB]))
    triangles = np.concatenate(pieces).astype(np.int64)
    if copies:
        vertices = np.concatenate([vertices, *copies])
    return Solid(vertices, triangles)


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
    )
