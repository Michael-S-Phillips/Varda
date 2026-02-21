"""
Unit tests for DataSource implementations.
"""

import numpy as np
import numpy.testing as npt
import pytest

from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.image_loading.data_sources.in_memory_data_source import InMemoryDataSource
from varda.image_loading.varda_raster import VardaRaster, CompatMetadata


class TestArrayDataSource:
    """Tests for ArrayDataSource (raw numpy array backed DataSource)."""

    @pytest.fixture
    def sample_data(self):
        """Create sample (h, w, bands) data."""
        np.random.seed(42)
        return np.random.rand(10, 20, 5).astype(np.float32)

    @pytest.fixture
    def ds(self, sample_data):
        """Create an ArrayDataSource from sample data."""
        return ArrayDataSource(
            sample_data,
            filePath="/test/image.tif",
            wavelengths=np.array([400.0, 500.0, 600.0, 700.0, 800.0]),
            wavelengthUnits="nm",
        )

    def test_dimensions(self, ds):
        assert ds.height == 10
        assert ds.width == 20
        assert ds.bandCount == 5

    def test_dtype(self, ds):
        assert ds.dtype == np.float32

    def test_file_path(self, ds):
        assert ds.filePath == "/test/image.tif"

    def test_wavelengths(self, ds):
        npt.assert_array_equal(ds.wavelengths, [400.0, 500.0, 600.0, 700.0, 800.0])
        assert ds.wavelengthsType is float
        assert ds.wavelengthUnits == "nm"

    def test_band_names_default(self, ds):
        assert ds.bandNames == [f"Band {i + 1}" for i in range(5)]

    def test_getBands(self, ds, sample_data):
        result = ds.getBands([0, 2, 4])
        assert result.shape == (10, 20, 3)
        npt.assert_array_equal(result[:, :, 0], sample_data[:, :, 0])
        npt.assert_array_equal(result[:, :, 1], sample_data[:, :, 2])
        npt.assert_array_equal(result[:, :, 2], sample_data[:, :, 4])

    def test_getBands_single(self, ds, sample_data):
        result = ds.getBands([3])
        assert result.shape == (10, 20, 1)
        npt.assert_array_equal(result[:, :, 0], sample_data[:, :, 3])

    def test_getPixelSpectrum(self, ds, sample_data):
        result = ds.getPixelSpectrum(5, 3)
        assert result.shape == (5,)
        npt.assert_array_equal(result, sample_data[3, 5, :])

    def test_getPixelSpectrum_out_of_bounds(self, ds):
        with pytest.raises(IndexError):
            ds.getPixelSpectrum(-1, 0)
        with pytest.raises(IndexError):
            ds.getPixelSpectrum(0, -1)
        with pytest.raises(IndexError):
            ds.getPixelSpectrum(20, 0)
        with pytest.raises(IndexError):
            ds.getPixelSpectrum(0, 10)

    def test_getData_all(self, ds, sample_data):
        result = ds.getData()
        assert result.shape == (10, 20, 5)
        npt.assert_array_equal(result, sample_data)

    def test_getData_with_bands(self, ds, sample_data):
        result = ds.getData(bandIndices=[1, 3])
        assert result.shape == (10, 20, 2)
        npt.assert_array_equal(result[:, :, 0], sample_data[:, :, 1])
        npt.assert_array_equal(result[:, :, 1], sample_data[:, :, 3])

    def test_getData_with_window(self, ds, sample_data):
        # window = (row_off, col_off, height, width)
        result = ds.getData(window=(2, 5, 3, 4))
        assert result.shape == (3, 4, 5)
        npt.assert_array_equal(result, sample_data[2:5, 5:9, :])

    def test_getData_with_bands_and_window(self, ds, sample_data):
        result = ds.getData(bandIndices=[0, 4], window=(1, 2, 3, 4))
        assert result.shape == (3, 4, 2)
        npt.assert_array_equal(result[:, :, 0], sample_data[1:4, 2:6, 0])
        npt.assert_array_equal(result[:, :, 1], sample_data[1:4, 2:6, 4])

    def test_readAllBands(self, ds, sample_data):
        result = ds.readAllBands()
        assert result.shape == (10, 20, 5)
        npt.assert_array_equal(result, sample_data)

    def test_getitem_full_slice(self, ds, sample_data):
        result = ds[:, :, :]
        npt.assert_array_equal(result, sample_data)

    def test_getitem_spatial_slice(self, ds, sample_data):
        result = ds[2:5, 3:8, :]
        assert result.shape == (3, 5, 5)
        npt.assert_array_equal(result, sample_data[2:5, 3:8, :])

    def test_getitem_band_slice(self, ds, sample_data):
        result = ds[:, :, 0:2]
        assert result.shape == (10, 20, 2)
        npt.assert_array_equal(result, sample_data[:, :, 0:2])

    def test_2d_data_expanded(self):
        data = np.random.rand(10, 20)
        ds = ArrayDataSource(data)
        assert ds.bandCount == 1
        assert ds.height == 10
        assert ds.width == 20

    def test_defaultBands(self):
        data = np.random.rand(10, 20, 5)
        ds = ArrayDataSource(data)
        npt.assert_array_equal(ds.defaultBands, [0, 1, 2])

    def test_defaultBands_single_band(self):
        data = np.random.rand(10, 20, 1)
        ds = ArrayDataSource(data)
        npt.assert_array_equal(ds.defaultBands, [0, 0, 0])

    def test_close_is_noop(self, ds):
        ds.close()  # Should not raise

    def test_coordinate_transform_identity(self, ds):
        # Default transform is identity
        x, y = ds.pixelToGeo(5, 3)
        assert x == 5.0
        assert y == 3.0
        col, row = ds.geoToPixel(5.0, 3.0)
        assert col == 5
        assert row == 3


class TestInMemoryDataSource:
    """Tests for InMemoryDataSource (thin wrapper around another DataSource)."""

    @pytest.fixture
    def source(self):
        """Create an ArrayDataSource to wrap."""
        np.random.seed(42)
        data = np.random.rand(10, 20, 5).astype(np.float32)
        return ArrayDataSource(
            data,
            filePath="/test/image.tif",
            wavelengths=np.array([400.0, 500.0, 600.0, 700.0, 800.0]),
            wavelengthUnits="nm",
            driver="GTiff",
            nodata=-9999.0,
        )

    @pytest.fixture
    def ds(self, source):
        """Create an InMemoryDataSource wrapping the source."""
        return InMemoryDataSource(source)

    def test_delegates_metadata(self, ds, source):
        assert ds.filePath == source.filePath
        assert ds.wavelengthUnits == source.wavelengthUnits
        assert ds.driver == source.driver
        assert ds.nodata == source.nodata
        npt.assert_array_equal(ds.wavelengths, source.wavelengths)
        npt.assert_array_equal(ds.defaultBands, source.defaultBands)

    def test_dimensions(self, ds):
        assert ds.height == 10
        assert ds.width == 20
        assert ds.bandCount == 5

    def test_data_matches_source(self, ds, source):
        npt.assert_array_equal(ds.readAllBands(), source.readAllBands())

    def test_getBands(self, ds, source):
        result = ds.getBands([0, 2, 4])
        expected = source.getBands([0, 2, 4])
        assert result.shape == (10, 20, 3)
        npt.assert_array_equal(result, expected)

    def test_getPixelSpectrum(self, ds, source):
        result = ds.getPixelSpectrum(5, 3)
        expected = source.getPixelSpectrum(5, 3)
        npt.assert_array_equal(result, expected)

    def test_getData_with_window(self, ds, source):
        result = ds.getData(window=(2, 5, 3, 4))
        expected = source.getData(window=(2, 5, 3, 4))
        npt.assert_array_equal(result, expected)

    def test_close_is_noop(self, ds):
        ds.close()  # Should not raise

    def test_coordinate_transform_delegates(self, ds, source):
        assert ds.pixelToGeo(5, 3) == source.pixelToGeo(5, 3)
        assert ds.geoToPixel(5.0, 3.0) == source.geoToPixel(5.0, 3.0)


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
            _dataSource=ds,
            name="test image",
            defaultBand=np.array([0, 1, 2], dtype=np.uint),
        )

    def test_basic_properties(self, raster):
        assert raster.width == 20
        assert raster.height == 10
        assert raster.bandCount == 5
        assert raster.name == "test image"
        assert raster.filePath == "/test/image.tif"

    def test_defaultBand(self, raster):
        npt.assert_array_equal(raster.defaultBand, [0, 1, 2])

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
        raster = VardaRaster(_dataSource=ds)
        assert raster.name == "myimage.tif"

    def test_loadIntoMemory(self, raster):
        mem = raster.loadIntoMemory()
        assert isinstance(mem, VardaRaster)
        assert mem.width == raster.width
        assert mem.height == raster.height
        assert mem.name == raster.name
        npt.assert_array_equal(mem.wavelengths, raster.wavelengths)

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
        )
        return VardaRaster(
            _dataSource=ds,
            name="test",
            defaultBand=np.array([0, 1, 2], dtype=np.uint),
            extraMetadata={"custom_key": "custom_value"},
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

    def test_metadata_defaultBand(self, raster):
        npt.assert_array_equal(raster.metadata.defaultBand, [0, 1, 2])

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


class TestRegistry:
    """Tests for the dynamic DataSource registry."""

    def test_registry_populated(self):
        from varda.image_loading.data_sources.registry import datasource_registry

        # At least ENVI, HDF5, and RasterioDataSource (TIFF + Common) should be registered
        assert len(datasource_registry) >= 4

    def test_registry_has_envi(self):
        from varda.image_loading.data_sources.registry import datasource_registry

        envi_entries = [e for e in datasource_registry if ".hdr" in e.fileExtensions]
        assert len(envi_entries) == 1
        assert envi_entries[0].formatName == "ENVI Image"

    def test_registry_has_hdf5(self):
        from varda.image_loading.data_sources.registry import datasource_registry

        hdf5_entries = [e for e in datasource_registry if ".h5" in e.fileExtensions]
        assert len(hdf5_entries) == 1
        assert hdf5_entries[0].formatName == "HDF5"

    def test_get_image_type_filter_dynamic(self):
        from varda.image_loading.data_sources.registry import get_image_type_filter

        filt = get_image_type_filter()
        assert "All Supported Images (*)" in filt
        assert "ENVI Image" in filt
        assert "HDF5" in filt
        assert "TIFF/GeoTIFF" in filt


class TestImageAlias:
    """Test that Image = VardaRaster alias works."""

    def test_entities_alias(self):
        from varda.common.entities import Image

        assert Image is VardaRaster

    def test_image_rendering_alias(self):
        from varda.image_rendering import Image

        assert Image is VardaRaster

    def test_create_via_alias(self):
        from varda.common.entities import Image

        ds = ArrayDataSource(np.zeros((5, 5, 3)))
        img = Image(_dataSource=ds, name="alias test")
        assert isinstance(img, VardaRaster)
        assert img.name == "alias test"
