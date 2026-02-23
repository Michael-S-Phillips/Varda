import pytest
import numpy as np
import numpy.testing as npt

from varda.image_loading.data_sources import ArrayDataSource
from varda.common.entities import VardaRaster, CompatMetadata


class TestVardaRaster:
    """Tests for VardaRaster entity."""

    @pytest.fixture
    def raster(self):
        np.random.seed(42)
        data = np.random.rand(10, 20, 5).astype(np.float32)
        ds = ArrayDataSource(
            data,
            filePath="/test/image.tif",
            wavelengths=np.array([400.0, 500.0, 600.0, 700.0, 800.0]),
        )
        return VardaRaster(
            dataSource=ds,
            name="test image",
        )

    def test_basic_properties(self, raster):
        assert raster.width == 20
        assert raster.height == 10
        assert raster.bandCount == 5
        assert raster.name == "test image"
        assert raster.filePath == "/test/image.tif"

    def test_defaultBands(self, raster):
        npt.assert_array_equal(raster.defaultBands, [0, 1, 2])

    def test_wavelengths(self, raster):
        npt.assert_array_equal(raster.wavelengths, [400.0, 500.0, 600.0, 700.0, 800.0])

    def test_getSpectrum(self, raster):
        spec = raster.getSpectrum(5, 3)
        assert spec.values.shape == (5,)
        npt.assert_array_equal(spec.wavelengths, [400.0, 500.0, 600.0, 700.0, 800.0])

    def test_getBands(self, raster):
        result = raster.getBands([0, 2])
        assert result.shape == (10, 20, 2)

    def test_getData(self, raster):
        result = raster.getData()
        assert result.shape == (10, 20, 5)

    def test_getitem(self, raster):
        result = raster[2:5, 3:8, 0:2]
        assert result.shape == (3, 5, 2)

    def test_name_from_filepath(self):
        ds = ArrayDataSource(
            np.zeros((5, 5, 3)),
            filePath="/some/path/myimage.tif",
        )
        raster = VardaRaster.fromDataSource(ds)
        assert raster.name == "myimage.tif"

    def test_close(self, raster):
        raster.close()  # Should not raise


class TestCompatMetadata:
    """Tests for CompatMetadata backward-compatibility layer."""

    @pytest.fixture
    def raster(self):
        ds = ArrayDataSource(
            np.zeros((10, 20, 5)),
            filePath="/test/image.tif",
            wavelengths=np.array([400.0, 500.0, 600.0, 700.0, 800.0]),
            wavelengthUnits="nm",
            driver="GTiff",
            nodata=-9999.0,
            defaultBands=np.array([0, 1, 2], dtype=np.uint),
            extraMetadata={"custom_key": "custom_value"},
        )
        return VardaRaster(
            dataSource=ds,
            name="test",
        )

    def test_metadata_property_returns_compat(self, raster):
        meta = raster.metadata
        assert isinstance(meta, CompatMetadata)

    def test_metadata_name(self, raster):
        assert raster.metadata.name == "test"

    def test_metadata_filePath(self, raster):
        assert raster.metadata.filePath == "/test/image.tif"

    def test_metadata_dimensions(self, raster):
        assert raster.metadata.width == 20
        assert raster.metadata.height == 10
        assert raster.metadata.bandCount == 5

    def test_metadata_wavelengths(self, raster):
        npt.assert_array_equal(
            raster.metadata.wavelengths, [400.0, 500.0, 600.0, 700.0, 800.0]
        )

    def test_metadata_wavelengths_type(self, raster):
        assert raster.metadata.wavelengths_type is float

    def test_metadata_defaultBands(self, raster):
        npt.assert_array_equal(raster.metadata.defaultBands, [0, 1, 2])

    def test_metadata_driver(self, raster):
        assert raster.metadata.driver == "GTiff"

    def test_metadata_dataIgnore(self, raster):
        assert raster.metadata.dataIgnore == -9999.0

    def test_metadata_hasGeospatialData(self, raster):
        # Default transform is identity, so no geospatial data
        assert raster.metadata.hasGeospatialData is False

    def test_metadata_extraMetadata(self, raster):
        assert raster.metadata.extraMetadata == {"custom_key": "custom_value"}

    def test_metadata_toFlatDict(self, raster):
        flat = raster.metadata.toFlatDict()
        assert flat["name"] == "test"
        assert flat["width"] == 20
        assert flat["custom_key"] == "custom_value"

    def test_metadata_iter(self, raster):
        items = dict(raster.metadata)
        assert items["name"] == "test"
        assert items["width"] == 20

    def test_metadata_getitem(self, raster):
        assert raster.metadata["name"] == "test"
        assert raster.metadata["width"] == 20
