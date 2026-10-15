"""Blending softens seams (visual products): feathering ramps across them,
multi-band blending mixes each scale over its own width. Far from a seam
the values stay the source's."""

import numpy as np
import pytest
from affine import Affine
from rasterio.crs import CRS

from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.mosaicking import render
from varda.mosaicking.grid import defaultGrid
from varda.mosaicking.model import MosaicProject
from varda.mosaicking.recipe import BlendMethod
from varda.mosaicking.render import renderMosaic
from varda.mosaicking.seams import SeamMethod, computeSeams

PIXEL = 10.0
ROWS = 40


def _strip(value, firstCol, cols, name):
    cube = np.full((ROWS, cols, 2), value, np.float32)
    cube[:, :, 1] *= 2
    source = ArrayDataSource(
        cube,
        wavelengths=np.array([500.0, 600.0]),
        wavelengthUnits="nm",
        transform=Affine(PIXEL, 0, firstCol * PIXEL, 0, -PIXEL, ROWS * PIXEL),
        crs=CRS.from_epsg(32612),
    )
    return VardaRaster(source, name=name)


def _project(seams=True) -> MosaicProject:
    """A flat 1.0 (columns 0-119) over a flat 2.0 (80-199); the seam at 100."""
    project = MosaicProject([_strip(1.0, 0, 120, "A"), _strip(2.0, 80, 120, "B")])
    if seams:
        project.setSeams(SeamMethod.VORONOI, computeSeams(project, SeamMethod.VORONOI))
    return project


def _row(project):
    return renderMosaic(project, defaultGrid(project)).cube[ROWS // 2, :, 0]


def test_without_blending_the_seam_is_a_step():
    row = _row(_project())
    assert row[99] == 1.0 and row[100] == 2.0


def test_feathering_ramps_across_the_seam():
    project = _project()
    project.setBlend(BlendMethod.FEATHER, width=20)
    row = _row(project)
    ramp = row[88:113]
    assert np.all(np.diff(ramp) >= -1e-6) and ramp[0] < ramp[-1]
    assert 1.4 < row[100] < 1.6  # halfway at the seam
    assert row[85] == 1.0 and row[115] == 2.0  # beyond half the width: the source
    assert np.all(row[:80] == 1.0) and np.all(row[120:] == 2.0)


def test_multiband_blending_smooths_the_step_and_keeps_the_rest():
    project = _project()
    project.setBlend(BlendMethod.MULTIBAND, levels=4)
    row = _row(project)
    assert 1.2 < row[100] < 1.8
    assert np.all(np.diff(row[80:120]) >= -1e-3)
    assert np.allclose(row[:50], 1.0, atol=1e-3) and np.allclose(
        row[150:], 2.0, atol=1e-3
    )


def _stacked() -> MosaicProject:
    """A flat 1.0 above a flat 2.0, overlapping in rows 20-29: the boundary
    runs along the rows, so tiles of rows cut across the blend."""

    def image(value, firstRow, name):
        cube = np.full((30, 50, 1), value, np.float32)
        source = ArrayDataSource(
            cube,
            wavelengths=np.array([500.0]),
            wavelengthUnits="nm",
            transform=Affine(PIXEL, 0, 0, 0, -PIXEL, (60 - firstRow) * PIXEL),
            crs=CRS.from_epsg(32612),
        )
        return VardaRaster(source, name=name)

    return MosaicProject([image(1.0, 0, "top"), image(2.0, 20, "bottom")])


@pytest.mark.parametrize("method", [BlendMethod.FEATHER, BlendMethod.MULTIBAND])
def test_tiles_join_without_a_trace(method, monkeypatch):
    project = _stacked()
    project.setBlend(method, width=20, levels=4)
    whole = renderMosaic(project, defaultGrid(project)).cube
    monkeypatch.setattr(render, "TILE_ROWS", 7)
    tiled = renderMosaic(project, defaultGrid(project)).cube
    assert np.allclose(whole, tiled, atol=1e-5, equal_nan=True)


def test_blending_without_seams_softens_the_stack_order_edge():
    project = _project(seams=False)
    project.setBlend(BlendMethod.FEATHER, width=10)
    row = _row(project)
    assert 1.0 < row[118] < 2.0  # A's edge, where B takes over
    assert row[100] == 1.0


def test_blending_is_visual_and_saved():
    project = _project()
    assert not project.isVisual
    project.setBlend(BlendMethod.FEATHER, width=12)
    assert project.isVisual
    other = _project()
    other.restore(project.state())
    assert other.blend.method is BlendMethod.FEATHER and other.blend.width == 12


def test_the_blend_scales_with_the_grid():
    project = _project()
    project.setBlend(BlendMethod.FEATHER, width=20)
    coarse = defaultGrid(project, PIXEL * 2)
    row = renderMosaic(project, coarse).cube[ROWS // 4, :, 0]
    # 20 px of the finest input are 10 px here: the ramp spans columns 45-55
    assert row[43] == 1.0 and row[57] == 2.0 and 1.0 < row[50] < 2.0
