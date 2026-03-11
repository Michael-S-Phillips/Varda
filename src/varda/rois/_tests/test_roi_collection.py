"""Tests for ROICollection and VardaROI."""

from types import SimpleNamespace

import numpy as np
import pytest
from PyQt6.QtGui import QColor
from shapely.geometry import Polygon, box

from varda.common.entities import ROIMode, VardaROI
from varda.rois.roi_collection import ROICollection

RED = QColor(255, 0, 0, 128)
GREEN = QColor(0, 255, 0, 128)
BLUE = QColor(0, 0, 255, 128)


@pytest.fixture
def collection() -> ROICollection:
    """An empty ROICollection with no CRS (pixel-space)."""
    return ROICollection()


@pytest.fixture
def sample_polygon() -> Polygon:
    return box(10, 20, 50, 60)


class TestVardaROI:
    def test_immutable(self, sample_polygon: Polygon) -> None:
        roi = VardaROI(
            fid=0,
            name="test",
            color=RED,
            geometry=sample_polygon,
            roiType=ROIMode.RECTANGLE,
        )
        with pytest.raises(AttributeError):
            roi.name = "changed"  # type: ignore[misc]

    def test_default_properties(self, sample_polygon: Polygon) -> None:
        roi = VardaROI(
            fid=0,
            name="test",
            color=RED,
            geometry=sample_polygon,
            roiType=ROIMode.POLYGON,
        )
        assert roi.properties == {}


class TestROICollectionCRUD:
    def test_add_roi(
        self, collection: ROICollection, sample_polygon: Polygon
    ) -> None:
        fid = collection.addROI(
            geometry=sample_polygon,
            name="ROI 1",
            color=RED,
            roiType=ROIMode.RECTANGLE,
        )
        assert fid == 0
        assert len(collection) == 1

    def test_add_multiple(
        self, collection: ROICollection, sample_polygon: Polygon
    ) -> None:
        fid1 = collection.addROI(sample_polygon, "A", RED, ROIMode.RECTANGLE)
        fid2 = collection.addROI(sample_polygon, "B", GREEN, ROIMode.POLYGON)
        assert fid1 != fid2
        assert len(collection) == 2

    def test_get_roi(
        self, collection: ROICollection, sample_polygon: Polygon
    ) -> None:
        fid = collection.addROI(sample_polygon, "ROI 1", RED, ROIMode.RECTANGLE)
        roi = collection.getROI(fid)
        assert isinstance(roi, VardaROI)
        assert roi.name == "ROI 1"
        assert roi.color == RED
        assert roi.roiType == ROIMode.RECTANGLE
        assert roi.geometry.equals(sample_polygon)

    def test_get_all_rois(
        self, collection: ROICollection, sample_polygon: Polygon
    ) -> None:
        collection.addROI(sample_polygon, "A", RED, ROIMode.RECTANGLE)
        collection.addROI(sample_polygon, "B", GREEN, ROIMode.POLYGON)
        rois = collection.getAllROIs()
        assert len(rois) == 2
        assert rois[0].name == "A"
        assert rois[1].name == "B"

    def test_remove_roi(
        self, collection: ROICollection, sample_polygon: Polygon
    ) -> None:
        fid = collection.addROI(sample_polygon, "ROI 1", RED, ROIMode.RECTANGLE)
        collection.removeROI(fid)
        assert len(collection) == 0
        with pytest.raises(KeyError):
            collection.getROI(fid)

    def test_remove_nonexistent(self, collection: ROICollection) -> None:
        with pytest.raises(KeyError):
            collection.removeROI(999)

    def test_update_roi(
        self, collection: ROICollection, sample_polygon: Polygon
    ) -> None:
        fid = collection.addROI(sample_polygon, "ROI 1", RED, ROIMode.RECTANGLE)
        collection.updateROI(fid, name="Renamed")
        roi = collection.getROI(fid)
        assert roi.name == "Renamed"

    def test_update_rejects_user_columns(
        self, collection: ROICollection, sample_polygon: Polygon
    ) -> None:
        fid = collection.addROI(sample_polygon, "ROI 1", RED, ROIMode.RECTANGLE)
        with pytest.raises(ValueError, match="not a core"):
            collection.updateROI(fid, custom_field="value")


class TestROICollectionUserColumns:
    def test_add_column(
        self, collection: ROICollection, sample_polygon: Polygon
    ) -> None:
        fid = collection.addROI(sample_polygon, "ROI 1", RED, ROIMode.RECTANGLE)
        collection.addColumn("material", default="unknown")
        assert collection.getProperty(fid, "material") == "unknown"

    def test_set_property(
        self, collection: ROICollection, sample_polygon: Polygon
    ) -> None:
        fid = collection.addROI(sample_polygon, "ROI 1", RED, ROIMode.RECTANGLE)
        collection.addColumn("material")
        collection.setProperty(fid, "material", "iron")
        assert collection.getProperty(fid, "material") == "iron"

    def test_set_property_rejects_core_columns(
        self, collection: ROICollection, sample_polygon: Polygon
    ) -> None:
        fid = collection.addROI(sample_polygon, "ROI 1", RED, ROIMode.RECTANGLE)
        with pytest.raises(ValueError, match="core column"):
            collection.setProperty(fid, "name", "bad")

    def test_user_properties_in_snapshot(
        self, collection: ROICollection, sample_polygon: Polygon
    ) -> None:
        collection.addColumn("material", default="unknown")
        fid = collection.addROI(sample_polygon, "ROI 1", RED, ROIMode.RECTANGLE)
        collection.setProperty(fid, "material", "iron")
        roi = collection.getROI(fid)
        assert roi.properties["material"] == "iron"

    def test_duplicate_column_raises(
        self, collection: ROICollection
    ) -> None:
        collection.addColumn("material")
        with pytest.raises(ValueError, match="already exists"):
            collection.addColumn("material")


class TestROICollectionSignals:
    def test_add_signal(
        self, collection: ROICollection, sample_polygon: Polygon
    ) -> None:
        received: list[int] = []
        collection.sigROIAdded.connect(received.append)
        fid = collection.addROI(sample_polygon, "ROI 1", RED, ROIMode.RECTANGLE)
        assert received == [fid]

    def test_remove_signal(
        self, collection: ROICollection, sample_polygon: Polygon
    ) -> None:
        received: list[int] = []
        collection.sigROIRemoved.connect(received.append)
        fid = collection.addROI(sample_polygon, "ROI 1", RED, ROIMode.RECTANGLE)
        collection.removeROI(fid)
        assert received == [fid]

    def test_update_signal(
        self, collection: ROICollection, sample_polygon: Polygon
    ) -> None:
        received: list[int] = []
        collection.sigROIUpdated.connect(received.append)
        fid = collection.addROI(sample_polygon, "ROI 1", RED, ROIMode.RECTANGLE)
        collection.updateROI(fid, name="Renamed")
        assert received == [fid]

    def test_collection_changed_signal(
        self, collection: ROICollection, sample_polygon: Polygon
    ) -> None:
        count = [0]
        collection.sigCollectionChanged.connect(lambda: count.__setitem__(0, count[0] + 1))
        collection.addROI(sample_polygon, "ROI 1", RED, ROIMode.RECTANGLE)
        collection.addROI(sample_polygon, "ROI 2", GREEN, ROIMode.POLYGON)
        assert count[0] == 2


class TestROICollectionFids:
    def test_fids_property(
        self, collection: ROICollection, sample_polygon: Polygon
    ) -> None:
        f1 = collection.addROI(sample_polygon, "A", RED, ROIMode.RECTANGLE)
        f2 = collection.addROI(sample_polygon, "B", GREEN, ROIMode.POLYGON)
        assert collection.fids == [f1, f2]

    def test_fids_after_remove(
        self, collection: ROICollection, sample_polygon: Polygon
    ) -> None:
        f1 = collection.addROI(sample_polygon, "A", RED, ROIMode.RECTANGLE)
        f2 = collection.addROI(sample_polygon, "B", GREEN, ROIMode.POLYGON)
        collection.removeROI(f1)
        assert collection.fids == [f2]


def _make_fake_image(width: int = 100, height: int = 100):
    """Create a minimal fake image object for testing pixel-space operations."""
    return SimpleNamespace(width=width, height=height)


class TestPixelCoordinates:
    def test_pixel_space_returns_coords(self, collection: ROICollection) -> None:
        poly = Polygon([(5, 10), (15, 10), (15, 20), (5, 20), (5, 10)])
        fid = collection.addROI(poly, "test", RED, ROIMode.POLYGON)
        coords = collection.getPixelCoordinates(fid)
        # Polygon exterior includes closing vertex
        assert coords.shape == (5, 2)
        np.testing.assert_array_almost_equal(coords[0], [5, 10])

    def test_nonexistent_fid(self, collection: ROICollection) -> None:
        with pytest.raises(KeyError):
            collection.getPixelCoordinates(999)


class TestMask:
    def test_mask_shape_and_content(self, collection: ROICollection) -> None:
        # A 10x10 box in pixel space inside a 100x100 image
        poly = box(10, 20, 20, 30)
        fid = collection.addROI(poly, "box", RED, ROIMode.RECTANGLE)
        image = _make_fake_image(100, 100)
        mask = collection.getMask(fid, image)

        assert mask.shape == (100, 100)
        assert mask.dtype == bool
        # Center of the box should be True
        assert mask[25, 15] is np.True_
        # Outside the box should be False
        assert mask[0, 0] is np.False_

    def test_mask_pixel_count(self, collection: ROICollection) -> None:
        # A box from (0,0) to (10,10) -- should cover ~100 pixels
        poly = box(0, 0, 10, 10)
        fid = collection.addROI(poly, "box", RED, ROIMode.RECTANGLE)
        image = _make_fake_image(50, 50)
        mask = collection.getMask(fid, image)
        # rasterize may differ slightly at edges, but should be ~100
        assert 80 <= mask.sum() <= 121


def _make_fake_image_with_data(
    width: int, height: int, bands: int, fill_value: float = 5.0
):
    """Fake image that returns constant data for all bands."""
    data = np.full((height, width, bands), fill_value, dtype=np.float64)
    return SimpleNamespace(
        width=width,
        height=height,
        bandCount=bands,
        nodata=None,
        wavelengths=np.arange(bands, dtype=np.float64),
        getData=lambda bandIndices=None, window=None: (
            data[window[0] : window[0] + window[2], window[1] : window[1] + window[3], :]
            if window is not None
            else data
        ),
    )


class TestSpectralStatistics:
    def test_mean_spectrum(self, collection: ROICollection) -> None:
        poly = box(2, 2, 8, 8)
        fid = collection.addROI(poly, "roi", RED, ROIMode.RECTANGLE)
        image = _make_fake_image_with_data(20, 20, 3, fill_value=7.0)
        spectrum = collection.getMeanSpectrum(fid, image)
        np.testing.assert_array_almost_equal(spectrum.values, [7.0, 7.0, 7.0])

    def test_std_deviation_constant(self, collection: ROICollection) -> None:
        poly = box(2, 2, 8, 8)
        fid = collection.addROI(poly, "roi", RED, ROIMode.RECTANGLE)
        image = _make_fake_image_with_data(20, 20, 3, fill_value=7.0)
        std = collection.getStdDeviation(fid, image)
        np.testing.assert_array_almost_equal(std, [0.0, 0.0, 0.0])

    def test_roi_statistics_keys(self, collection: ROICollection) -> None:
        poly = box(2, 2, 8, 8)
        fid = collection.addROI(poly, "roi", RED, ROIMode.RECTANGLE)
        image = _make_fake_image_with_data(20, 20, 3, fill_value=5.0)
        stats = collection.getROIStatistics(fid, image)
        assert set(stats.keys()) == {"mean", "std", "min", "max", "pixel_count"}
        assert stats["pixel_count"] > 0
        np.testing.assert_array_almost_equal(stats["min"], [5.0, 5.0, 5.0])
        np.testing.assert_array_almost_equal(stats["max"], [5.0, 5.0, 5.0])


class TestFileIO:
    def test_geojson_round_trip(self, collection: ROICollection, tmp_path) -> None:
        poly1 = box(0, 0, 10, 10)
        poly2 = box(20, 20, 30, 30)
        collection.addROI(poly1, "ROI A", RED, ROIMode.RECTANGLE)
        collection.addROI(poly2, "ROI B", QColor(0, 255, 0, 200), ROIMode.POLYGON)

        path = str(tmp_path / "rois.geojson")
        collection.toFile(path)

        loaded = ROICollection.fromFile(path)
        assert len(loaded) == 2
        rois = loaded.getAllROIs()
        assert rois[0].name == "ROI A"
        assert rois[0].color == RED
        assert rois[0].roiType == ROIMode.RECTANGLE
        assert rois[0].geometry.equals(poly1)
        assert rois[1].name == "ROI B"
        assert rois[1].color == QColor(0, 255, 0, 200)

    def test_gpkg_round_trip(self, collection: ROICollection, tmp_path) -> None:
        poly = box(5, 5, 15, 15)
        collection.addROI(poly, "Test", QColor(100, 100, 100, 255), ROIMode.FREEHAND)

        path = str(tmp_path / "rois.gpkg")
        collection.toFile(path)

        loaded = ROICollection.fromFile(path)
        assert len(loaded) == 1
        roi = loaded.getROI(0)
        assert roi.name == "Test"
        assert roi.roiType == ROIMode.FREEHAND

    def test_export_empty_collection(self, collection: ROICollection, tmp_path) -> None:
        path = str(tmp_path / "empty.geojson")
        collection.toFile(path)
        # Should not create file (just warns)
        import os
        assert not os.path.exists(path)


class TestApplyToImage:
    def test_apply_same_crs(self) -> None:
        from pyproj import CRS
        from affine import Affine

        crs = CRS.from_epsg(4326)
        source = ROICollection(crs=crs, transform=Affine.identity())
        poly = box(10, 20, 30, 40)
        source.addROI(poly, "A", RED, ROIMode.RECTANGLE)

        target_image = SimpleNamespace(
            crs=crs,
            transform=Affine.identity(),
            width=100,
            height=100,
        )
        result = source.applyToImage(target_image)
        assert len(result) == 1
        roi = result.getROI(0)
        assert roi.name == "A"
        assert roi.geometry.equals(poly)

    def test_apply_no_crs_raises(self, collection: ROICollection) -> None:
        poly = box(0, 0, 10, 10)
        collection.addROI(poly, "A", RED, ROIMode.RECTANGLE)
        target = SimpleNamespace(crs=None, transform=None)
        with pytest.raises(ValueError, match="pixel-space"):
            collection.applyToImage(target)
