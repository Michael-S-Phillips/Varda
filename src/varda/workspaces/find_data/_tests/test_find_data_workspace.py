"""The Find Data workspace with a stand-in catalog: search, map, selection,
basemap, overlays and sessions."""

from datetime import datetime, timezone

import geopandas as gpd
import numpy as np
import pytest
import shapely
from affine import Affine

from varda.catalogs import registry
from varda.catalogs.bodies import geographicCrs
from varda.catalogs.catalog import Catalog, Collection, Product, SearchPage
from varda.common.entities import VardaRaster
from varda.common.parameter import FloatParameter
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.workspaces.find_data.find_data_workspace import AREA_BOX, FindDataWorkspace

PRODUCTS = [
    Product(
        "obs_a",
        "Observation A",
        "mars_obs",
        shapely.box(77.0, 18.0, 77.5, 18.5),
        datetime(2007, 1, 29, tzinfo=timezone.utc),
        properties={"Incidence (°)": 55.0},
    ),
    Product(
        "obs_b",
        "Observation B",
        "mars_obs",
        shapely.box(77.6, 18.2, 78.0, 18.7),
        properties={"Incidence (°)": 40.0},
    ),
]


class FakeCatalog(Catalog):
    catalogId = "fake"
    name = "Fake catalog"
    description = "Two observations on Mars."
    maxIncidence = FloatParameter("Max. incidence", 90.0, range=(0.0, 90.0))
    queries: list = []

    def collections(self):
        return [Collection("mars_obs", "Mars observations", "Mars")]

    def search(self, query, progress):
        FakeCatalog.queries.append(query)
        found = [
            p
            for p in PRODUCTS
            if query.bbox is None or p.footprint.intersects(shapely.box(*query.bbox))
        ]
        found = [
            p for p in found if p.properties["Incidence (°)"] <= self.maxIncidence.get()
        ]
        if query.page is None and len(found) > 1:
            return SearchPage(tuple(found[:1]), nextPage=1, total=len(found))
        return SearchPage(tuple(found[1:] if query.page else found), total=len(found))

    def files(self, product):
        return []


@pytest.fixture
def workspace(qtbot, monkeypatch):
    monkeypatch.setattr(registry, "catalogRegistry", [FakeCatalog])
    FakeCatalog.queries = []
    widget = FindDataWorkspace([])
    qtbot.addWidget(widget)
    qtbot.waitUntil(lambda: widget.collectionBox.count() == 1, timeout=5000)
    return widget


def _search(workspace, qtbot):
    workspace.searchButton.click()
    qtbot.waitUntil(lambda: workspace.searchButton.isEnabled(), timeout=5000)


def test_the_catalogs_collections_and_filters_are_offered(workspace):
    assert workspace.catalogBox.currentText() == "Fake catalog"
    assert workspace.collectionBox.currentText() == "Mars: Mars observations"
    assert workspace.bodyLabel.text() == "<b>Mars</b>"
    assert workspace.filters.layout().count() == 1  # the catalog's own filters


def test_a_search_fills_the_table_and_the_map_and_pages(workspace, qtbot):
    workspace.map.zoomTo((76.5, 17.5, 78.5, 19.0), padding=0)
    _search(workspace, qtbot)
    assert workspace.results.rowCount() == 1
    assert "1 of 2 products" in workspace.searchStatus.text()
    assert workspace.moreButton.isEnabled()
    x, _ = workspace.map.footprints.getData()
    assert np.nanmin(x) == pytest.approx(77.0)
    workspace.moreButton.click()
    qtbot.waitUntil(lambda: workspace.results.rowCount() == 2, timeout=5000)
    assert not workspace.moreButton.isEnabled()
    assert workspace.results.headers[3] == "Incidence (°)"


def test_the_filters_and_dates_reach_the_catalog(workspace, qtbot):
    workspace.catalog().maxIncidence.set(45.0)
    workspace.fromCheck.setChecked(True)
    workspace.areaBox.setCurrentText(AREA_BOX)
    workspace.map.setArea((77.5, 18.0, 78.5, 19.0))
    _search(workspace, qtbot)
    query = FakeCatalog.queries[-1]
    assert query.bbox == pytest.approx((77.5, 18.0, 78.5, 19.0))
    assert query.start is not None and query.end is None
    assert [p.id for p in workspace.results.products] == ["obs_b"]


def test_clicking_a_footprint_selects_it_and_shows_it(workspace, qtbot):
    workspace.map.zoomTo((76.5, 17.5, 78.5, 19.0), padding=0)
    _search(workspace, qtbot)
    workspace._onMapClicked(77.2, 18.2, False)
    assert [p.id for p in workspace.selectedProducts()] == ["obs_a"]
    assert (
        "obs_a" in workspace.details.text() and "Incidence" in workspace.details.text()
    )
    x, _ = workspace.map.selected.getData()
    assert len(x) > 0


def test_a_mars_image_becomes_the_basemap(workspace, qtbot, monkeypatch):
    crs = geographicCrs("Mars")
    image = VardaRaster(
        ArrayDataSource(
            np.random.default_rng(0).random((50, 60, 3)).astype(np.float32),
            wavelengths=np.array([400.0, 500.0, 600.0]),
            transform=Affine(0.05, 0, 76.5, 0, -0.05, 19.5),
            crs=crs,
        ),
        name="mars image",
    )
    workspace.projectImages.append(image)
    workspace._onCollection()
    assert workspace.basemapBox.count() == 2
    workspace.basemapBox.setCurrentIndex(1)
    qtbot.waitUntil(lambda: workspace.map.basemapItem.image is not None, timeout=10000)
    rect = workspace.map.basemapItem.boundingRect()
    assert rect.width() > 0


def test_overlays_are_drawn_and_saved(workspace, tmp_path):
    traverse = gpd.GeoDataFrame(
        geometry=[shapely.LineString([(77.4, 18.4), (77.5, 18.5)])],
        crs=geographicCrs("Mars"),
    )
    traverse.to_file(tmp_path / "traverse.gpkg", driver="GPKG")
    workspace.addOverlay(str(tmp_path / "traverse.gpkg"))
    assert workspace.map._overlays and workspace.overlayPaths == [
        str(tmp_path / "traverse.gpkg")
    ]


def test_the_workspace_comes_back_from_a_session(workspace, qtbot, tmp_path):
    workspace.areaBox.setCurrentText(AREA_BOX)
    workspace.map.setArea((77.0, 18.0, 78.0, 19.0))
    state = workspace.sessionState()
    reopened = FindDataWorkspace([])
    qtbot.addWidget(reopened)
    reopened.restoreSessionState(state)
    qtbot.waitUntil(lambda: reopened.collectionBox.count() == 1, timeout=5000)
    assert reopened.areaBox.currentText() == AREA_BOX
    assert reopened.map.areaBounds() == pytest.approx((77.0, 18.0, 78.0, 19.0))
