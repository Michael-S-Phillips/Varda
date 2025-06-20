import numpy as np
from core import ProjectContext
from core import Metadata, Band, Stretch


def test_project_context_add_image():
    proj = ProjectContext()
    raster = np.zeros((10, 10))
    metadata = Metadata()
    index = proj.createImage(raster, metadata)
    image = proj.getImage(index)
    assert len(proj.getAllImages()) == 1
    assert proj.getImage(0) is image


def test_project_context_remove_image():
    proj = ProjectContext()
    raster = np.zeros((10, 10))
    metadata = Metadata()
    index = proj.createImage(raster, metadata)
    image = proj.getImage(index)

    assert image.raster is raster
    assert image.metadata is metadata

    proj.removeImage(0)

    assert len(proj.getAllImages()) == 0


def test_project_context_update_metadata():
    proj = ProjectContext()
    raster = np.zeros((10, 10))
    metadata = Metadata(_driver="OldDriver")
    index = proj.createImage(raster, metadata)
    proj.updateMetadata(0, "driver", "NewDriver")
    assert proj.getImage(0).metadata.driver == "NewDriver"


def test_project_context_add_band():
    proj = ProjectContext()
    raster = np.zeros((10, 10))
    metadata = Metadata()
    band = Band.createDefault()
    index = proj.createImage(raster, metadata)

    bandIndex = proj.addBand(index, band)
    assert proj.getImage(index).band[bandIndex] is band


def test_project_context_add_stretch():
    proj = ProjectContext()
    raster = np.zeros((10, 10))
    metadata = Metadata()
    stretch = Stretch.createDefault()
    index = proj.createImage(raster, metadata)

    stretchIndex = proj.addStretch(index, stretch)
    assert proj.getImage(index).stretch[stretchIndex] is stretch
