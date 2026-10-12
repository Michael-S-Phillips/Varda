"""A small synthetic scene with known endmembers for hourglass tests."""

import numpy as np
from scipy.ndimage import gaussian_filter

from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource

WAVELENGTHS = np.linspace(1000.0, 2600.0, 80)


def endmemberSpectra() -> np.ndarray:
    """Three distinct reflectance spectra (3, bands)."""
    x = WAVELENGTHS
    flat = 0.45 + 0.0 * x
    clay = (
        0.6
        - 0.25 * np.exp(-0.5 * ((x - 2200.0) / 25.0) ** 2)
        - 0.1 * np.exp(-0.5 * ((x - 1900.0) / 40.0) ** 2)
    )
    mafic = 0.15 + 0.2 * (x - 1000.0) / 1600.0
    return np.stack([flat, clay, mafic])


def syntheticScene(rows=40, cols=36, seed=0) -> tuple[VardaRaster, np.ndarray]:
    """A scene mixed from ``endmemberSpectra`` with pure patches in three
    corners, and the (rows, cols, 3) true abundances. Pixel (0, 0) is nodata."""
    rng = np.random.default_rng(seed)
    E = endmemberSpectra()
    # spatially smooth mixtures, like a real scene (MNF's shift-difference
    # noise estimate relies on neighbouring pixels being similar)
    fields = gaussian_filter(rng.normal(size=(rows, cols, 3)), sigma=(4, 4, 0)) * 6.0
    weights = np.exp(fields)
    abundances = weights / weights.sum(axis=2, keepdims=True)
    for k, (r, c) in enumerate([(2, 2), (2, cols - 6), (rows - 6, 2)]):
        abundances[r : r + 4, c : c + 4] = np.eye(3)[k]
    cube = abundances @ E + 0.002 * rng.normal(size=(rows, cols, E.shape[1]))
    cube[0, 0, :] = -1.0
    source = ArrayDataSource(
        cube,
        wavelengths=WAVELENGTHS,
        wavelengthUnits="nm",
        nodata=-1.0,
        defaultBands=np.array([60, 40, 10]),
    )
    return VardaRaster(source, name="scene"), abundances
