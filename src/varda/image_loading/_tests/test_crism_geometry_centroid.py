"""Column lock must use the true footprint centre, whatever the vertex list looks like."""

import numpy as np

from varda.image_loading.crism_geometry import (
    ColumnGeometry,
    computeColumnLockedTranslation,
)


def _geometry():
    h, w = 10, 8
    ir = np.tile(np.arange(w, dtype=np.float64), (h, 1))
    return ColumnGeometry(ir_sample=ir)


def test_closing_vertex_does_not_bias_the_translation():
    geom = _geometry()
    openBox = np.array([[2, 1], [7, 1], [7, 6], [2, 6]], dtype=np.float64)
    # Stored ROI geometries repeat the first vertex to close the ring.
    closedBox = np.vstack([openBox, openBox[:1]])

    assert computeColumnLockedTranslation(
        openBox, clickRow=7, clickCol=0, geometry=geom
    ) == computeColumnLockedTranslation(
        closedBox, clickRow=7, clickCol=0, geometry=geom
    )
