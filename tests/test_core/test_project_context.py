import numpy as np
from core.data import ProjectContext
from core.entities import Image, Metadata, Band, Stretch


def test_project_context_add_image():
    pc = ProjectContext()
    raster = np.zeros((10, 10))
    metadata = Metadata()
    image = Image(_raster=raster, _metadata=metadata)

    pc.addImage(image)
    assert len(pc.getAllImages()) == 1
    assert pc.getImage(0) == image


def test_project_context_remove_image():
    pc = ProjectContext()
    raster = np.zeros((10, 10))
    metadata = Metadata()
    image = Image(_raster=raster, _metadata=metadata)
    pc.addImage(image)

    pc.removeImage(0)
    assert len(pc.getAllImages()) == 0


def test_project_context_update_metadata():
    pc = ProjectContext()
    raster = np.zeros((10, 10))
    metadata = Metadata(_driver="OldDriver")
    image = Image(_raster=raster, _metadata=metadata)

    pc.addImage(image)
    pc.updateMetadata(0, "driver", "NewDriver")
    assert pc.getImage(0).metadata.driver == "NewDriver"


def test_project_context_add_band():
    pc = ProjectContext()
    raster = np.zeros((10, 10))
    metadata = Metadata()
    band = Band.createDefault()
    image = Image(_raster=raster, _metadata=metadata)

    pc.addImage(image)
    pc.addBand(0, band)
    assert pc.getImage(0).band == [band]


def test_project_context_add_stretch():
    pc = ProjectContext()
    raster = np.zeros((10, 10))
    metadata = Metadata()
    stretch = Stretch.createDefault()
    image = Image(_raster=raster, _metadata=metadata)

    pc.addImage(image)
    pc.addStretch(0, stretch)
    assert pc.getImage(0).stretch == [stretch]
