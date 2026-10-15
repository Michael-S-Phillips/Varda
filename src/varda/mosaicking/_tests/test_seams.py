"""Seams: where each image takes over in an overlap. Voronoi splits it down
the middle; least difference follows where the images agree. Seams are
polygons in map coordinates, so they can be edited."""

import numpy as np
import pytest
from affine import Affine
from rasterio.crs import CRS
from scipy import ndimage

from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.mosaicking.grid import defaultGrid
from varda.mosaicking.model import MosaicProject
from varda.mosaicking.render import renderMosaic
from varda.mosaicking.seams import Seam, SeamMethod, computeSeams

PIXEL = 10.0
ROWS = 60


def _texture(seed=0, cols=200):
    rng = np.random.default_rng(seed)
    return ndimage.gaussian_filter(rng.normal(size=(ROWS, cols)), 2.0)


def _strip(cube, firstCol, name):
    source = ArrayDataSource(
        cube.astype(np.float32),
        wavelengths=np.array([500.0, 600.0]),
        wavelengthUnits="nm",
        transform=Affine(PIXEL, 0, firstCol * PIXEL, 0, -PIXEL, ROWS * PIXEL),
        crs=CRS.from_epsg(32612),
    )
    return VardaRaster(source, name=name)


def _project(b=None) -> MosaicProject:
    """A (columns 0-119) over B (columns 80-199): 40 columns of overlap."""
    scene = np.stack([_texture(), 0.5 * _texture()], axis=2)
    bCube = scene[:, 80:200] if b is None else b
    return MosaicProject([_strip(scene[:, :120], 0, "A"), _strip(bCube, 80, "B")])


def _sources(project):
    return renderMosaic(project, defaultGrid(project)).sources


def test_without_seams_the_top_image_takes_the_overlap():
    sources = _sources(_project())
    assert (sources[:, 80:120] == 0).all()


def test_voronoi_splits_the_overlap_down_the_middle():
    project = _project()
    project.setSeams(SeamMethod.VORONOI, computeSeams(project, SeamMethod.VORONOI))
    sources = _sources(project)
    assert (sources[:, 82:98] == 0).all()
    assert (sources[:, 102:118] == 1).all()


def test_least_difference_follows_where_the_images_agree():
    scene = np.stack([_texture(), 0.5 * _texture()], axis=2)
    rng = np.random.default_rng(3)
    b = scene[:, 80:200].copy()
    # B differs from A in the overlap except along a wavy path near column 92
    path = (92 + 3 * np.sin(np.arange(ROWS) / 6.0)).astype(int)
    noise = 0.3 * rng.normal(size=(ROWS, 40, 2))
    for row, col in enumerate(path):
        noise[row, col - 80] = 0.0
    b[:, :40] += noise
    project = _project(b)
    project.setSeams(
        SeamMethod.LEAST_DIFFERENCE, computeSeams(project, SeamMethod.LEAST_DIFFERENCE)
    )
    sources = _sources(project)
    for row, col in enumerate(path):
        assert (sources[row, 80 : col - 1] == 0).all(), row
        assert (sources[row, col + 2 : 120] == 1).all(), row


def test_spectra_stay_exact_across_a_seam():
    project = _project()
    project.setSeams(SeamMethod.VORONOI, computeSeams(project, SeamMethod.VORONOI))
    result = renderMosaic(project, defaultGrid(project))
    scene = np.stack([_texture(), 0.5 * _texture()], axis=2).astype(np.float32)
    assert np.array_equal(
        result.cube, scene
    )  # same scene: every pixel is a source pixel


def test_an_edited_seam_moves_the_boundary():
    project = _project()
    seams = computeSeams(project, SeamMethod.VORONOI)
    # give B the whole overlap: its region becomes the overlap's rectangle
    x0, x1, y0, y1 = 80 * PIXEL, 120 * PIXEL, 0.0, ROWS * PIXEL
    whole = np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]])
    project.setSeams(
        SeamMethod.VORONOI, [Seam(seams[0].top, seams[0].bottom, (whole,))]
    )
    assert (_sources(project)[:, 81:119] == 1).all()


def test_seams_survive_a_session():
    project = _project()
    project.setSeams(SeamMethod.VORONOI, computeSeams(project, SeamMethod.VORONOI))
    other = _project()
    other.restore(project.state())
    assert other.seamMethod is SeamMethod.VORONOI
    assert np.array_equal(_sources(other), _sources(project))
    other.clearSeams()
    assert not other.seams and other.seamMethod is SeamMethod.PRIORITY


def test_images_that_do_not_overlap_get_no_seam():
    project = _project()
    project.nudge(1, 5000.0, 0.0)
    assert computeSeams(project, SeamMethod.VORONOI) == []


@pytest.mark.parametrize("method", [SeamMethod.VORONOI, SeamMethod.LEAST_DIFFERENCE])
def test_three_images_get_a_seam_per_overlap(method):
    scene = np.stack([_texture(cols=300), 0.5 * _texture(cols=300)], axis=2)
    project = MosaicProject(
        [
            _strip(scene[:, 0:120], 0, "A"),
            _strip(scene[:, 90:210], 90, "B"),
            _strip(scene[:, 180:300], 180, "C"),
        ]
    )
    seams = computeSeams(project, method)
    assert {(s.top, s.bottom) for s in seams} == {(0, 1), (1, 2)}
    project.setSeams(method, seams)
    sources = _sources(project)
    assert (
        (sources[:, :90] == 0).all()
        and (sources[:, 120:180] == 1).all()
        and (sources[:, 210:] == 2).all()
    )
