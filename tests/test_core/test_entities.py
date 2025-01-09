import pytest
import numpy as np
from core.entities import Image, Metadata, Band, Stretch
from core.data import ProjectContext


def test_band_defaults():
    band = Band.createDefault()
    assert band.name == "default"
    assert band.r == 0
    assert band.g == 0
    assert band.b == 0


def test_band_custom():
    band = Band(name="custom", r=1, g=2, b=3)
    assert band.name == "custom"
    assert band.r == 1
    assert band.g == 2
    assert band.b == 3


def test_stretch_defaults():
    stretch = Stretch.createDefault()
    assert stretch.name == "default"
    assert stretch.minR == 0
    assert stretch.maxR == 1


def test_stretch_custom():
    stretch = Stretch(
        name="custom", minR=10, maxR=20, minG=15, maxG=25, minB=5, maxB=10
    )
    assert stretch.name == "custom"
    assert stretch.minR == 10
    assert stretch.maxR == 20


def test_metadata_defaults():
    metadata = Metadata()
    assert metadata.driver == ""
    assert metadata.width == 0
    assert metadata.height == 0
    assert metadata.bandCount == 0


def test_metadata_custom():
    wavelength = np.array([450, 550, 650])
    metadata = Metadata(
        _driver="GTiff", _width=100, _height=200, _bandCount=3, _wavelength=wavelength
    )
    assert metadata.driver == "GTiff"
    assert metadata.width == 100
    assert metadata.height == 200
    assert (metadata.wavelength == wavelength).all()


def test_image_creation():
    raster = np.zeros((10, 10))
    metadata = Metadata()
    image = Image(raster, metadata, [], [], 0)
    assert (image.raster == raster).all()
    assert image.metadata == metadata
