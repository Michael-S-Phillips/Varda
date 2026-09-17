"""writeRaster saves a VardaRaster to disk with the metadata Varda reads back."""

import numpy as np
import pytest
from affine import Affine
from pyproj import CRS

from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.image_loading.image_loading_service import openDataSource
from varda.image_loading.raster_writer import writeRaster


def _spectralImage() -> VardaRaster:
    rng = np.random.default_rng(3)
    cube = rng.random((5, 7, 4)).astype(np.float32)
    cube[0, 0, :] = -9999.0
    source = ArrayDataSource(
        cube,
        wavelengths=np.array([450.0, 550.0, 650.0, 750.0]),
        wavelengthUnits="nm",
        bandNames=["blue", "green", "red", "nir"],
        transform=Affine(10.0, 0.0, 100.0, 0.0, -10.0, 200.0),
        crs=CRS.from_epsg(32612),
        nodata=-9999.0,
        defaultBands=np.array([2, 1, 0]),
        description="a test scene",
    )
    return VardaRaster(source, name="scene")


def test_envi_round_trip_keeps_data_and_spectral_metadata(tmp_path):
    image = _spectralImage()

    written = writeRaster(image, tmp_path / "scene.hdr")

    assert written == tmp_path / "scene.img"
    assert (tmp_path / "scene.hdr").exists()
    loaded = openDataSource(str(written))
    data = loaded.readAllBands()  # nodata pixels come back masked as NaN
    np.testing.assert_array_equal(data[1:], image.getData()[1:])
    assert np.isnan(data[0, 0]).all()
    np.testing.assert_array_equal(loaded.wavelengths, image.wavelengths)
    assert loaded.wavelengthUnits == "nm"
    assert loaded.bandNames == ["blue", "green", "red", "nir"]
    assert list(loaded.defaultBands) == [2, 1, 0]
    assert loaded.nodata == -9999.0
    assert loaded.transform == image.transform
    assert loaded.crs is not None and loaded.crs.to_epsg() == 32612


def test_envi_round_trip_of_a_parameter_image_keeps_its_band_labels(tmp_path):
    names = ["BD1900", "OLINDEX3", "R770"]
    source = ArrayDataSource(
        np.zeros((3, 3, 3), dtype=np.float32),
        wavelengths=np.array(names),
        wavelengthUnits="parameters",
        bandNames=names,
        isParameterImage=True,
    )
    image = VardaRaster(source, name="params")

    written = writeRaster(image, tmp_path / "params")  # no suffix: ENVI by default

    assert written == tmp_path / "params.img"
    loaded = openDataSource(str(written))
    assert loaded.isParameterImage
    assert loaded.bandNames == names
    assert list(loaded.wavelengths) == names


def test_geotiff_round_trip_keeps_data_and_georeferencing(tmp_path):
    image = _spectralImage()

    written = writeRaster(image, tmp_path / "scene.tif")

    assert written == tmp_path / "scene.tif"
    loaded = openDataSource(str(written))
    data = loaded.readAllBands()  # nodata pixels come back masked as NaN
    np.testing.assert_array_equal(data[1:], image.getData()[1:])
    assert np.isnan(data[0, 0]).all()
    assert loaded.nodata == -9999.0
    assert loaded.bandNames == ["blue", "green", "red", "nir"]
    np.testing.assert_array_equal(loaded.wavelengths, image.wavelengths)
    assert loaded.transform == image.transform
    assert loaded.crs is not None and loaded.crs.to_epsg() == 32612


def test_unknown_extension_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="\\.png"):
        writeRaster(_spectralImage(), tmp_path / "scene.png")
