import logging

import numpy as np

logger = logging.getLogger(__name__)


class RegionCoordinateTransform:
    """
    Handles 2D coordinate transformations between local ROI space and global image space. using affine transformations.
    Note that the methods accept x, y coordinates, since that's the most convenient.
    but internally the calculations are done in row, col order by swapping the axes.
    """

    def __init__(self, origin, basisVectors):
        """
        Initialize the transform with origin and basis vectors.

        Args:
            origin: (row, col) array defining the origin in global coordinates
            basisVectors: Two (row, col) arrays defining the basis vectors in global coordinates
        """
        self.origin = np.asarray(origin)
        self.vx, self.vy = map(np.asarray, basisVectors)

    def localToGlobal(self, coords) -> np.ndarray:
        """
        convert a set of local coordinates to global coordinates.

        Args:
            coords: (..., (x, y)) array of local coordinates to convert.
        Returns:
            (..., (x, y)) array of global coordinates
        """
        coords = np.asarray(coords)

        # convert (..., (x, y)) to (..., (row, col))
        col = coords[..., 0]
        row = coords[..., 1]

        # compute in (row, col) space
        rc = self.origin + row[..., None] * self.vx + col[..., None] * self.vy
        # rc[...,0] is row, rc[...,1] is col

        # return as (x, y) = (col, row)
        return np.stack([rc[..., 1], rc[..., 0]], axis=-1)

    def globalToLocal(self, coords) -> np.ndarray:
        """
        convert a set of global coordinates to local coordinates.

        Args:
            coords: (..., (x, y)) array of global coordinates to convert
        Returns:
            (..., (x, y)) array of local coordinates
        """
        coords = np.asarray(coords)
        # convert (..., (x, y)) to (..., (row, col))
        col = coords[..., 0]
        row = coords[..., 1]
        rc = np.stack([row, col], axis=-1)

        # subtract origin in (row, col)
        delta = rc - self.origin

        # solve M @ [r; c] = delta for [r, c]
        M = np.column_stack((self.vx, self.vy))  # shape (2,2)
        local_rc = np.linalg.solve(M, delta.T).T  # gives (row, col)

        # swap back to (x, y) = (col, row)
        return np.stack([local_rc[..., 1], local_rc[..., 0]], axis=-1)
