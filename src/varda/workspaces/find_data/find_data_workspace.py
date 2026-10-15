"""Find Data: search a catalog for observations of a place, see their
footprints on a map, and pick what to download. Varda knows no missions:
the catalogs (``varda.catalogs``, and plugins' ``registerCatalogs``) do."""

from __future__ import annotations

from collections.abc import MutableSequence
from datetime import datetime, timezone

import geopandas as gpd
import PyQt6Ads as ads
import shapely
from PyQt6.QtCore import QDate, QSortFilterProxyModel, Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDateEdit,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QPushButton,
    QSpinBox,
    QStatusBar,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from varda.catalogs.bodies import toLongitudeLatitude
from varda.catalogs.catalog import Catalog, Collection, Product, SearchPage, SearchQuery
from varda.catalogs.footprints import FootprintFileCatalog
from varda.catalogs.http import fetchBytes
from varda.catalogs.registry import availableCatalogs
from varda.common.entities import VardaRaster
from varda.common.parameter_widgets import groupWidget
from varda.common.ui import MutedLabel, VardaDockWidget
from varda.utilities.background import runInBackground
from varda.workspaces.find_data.basemap import basemap, imageBody, imageBounds
from varda.workspaces.find_data.map_view import FootprintMap
from varda.workspaces.find_data.results_model import SORT_ROLE, ResultsModel

AREA_VIEW, AREA_BOX, AREA_IMAGE = "Map view", "Box on the map", "An image's footprint"
DEFAULT_LIMIT = 100


class FindDataWorkspace(QMainWindow):
    def __init__(
        self,
        projectImages: MutableSequence[VardaRaster] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Find Data")
        self.projectImages = projectImages if projectImages is not None else []
        self._catalogs: dict[str, Catalog] = {}  # one each, so filters persist
        self._collections: list[Collection] = []
        self._query: SearchQuery | None = None
        self._nextPage: object | None = None
        self.overlayPaths: list[str] = []

        self.map = FootprintMap()
        self.map.sigClicked.connect(self._onMapClicked)
        self.results = ResultsModel(self)
        self.proxy = QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.results)
        self.proxy.setSortRole(SORT_ROLE)
        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        header = self.table.horizontalHeader()
        assert header is not None
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        selection = self.table.selectionModel()
        assert selection is not None
        selection.selectionChanged.connect(lambda *_: self._onSelection())
        self.table.doubleClicked.connect(lambda _: self._zoomToSelection())

        self._buildSearchPanel()
        self._buildMapBar()
        self._buildPreview()
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self._buildDocks()
        self._onCatalog()

    # --- layout ---------------------------------------------------------------------

    def _buildSearchPanel(self) -> None:
        self.catalogBox = QComboBox()
        for catalog in availableCatalogs():
            self.catalogBox.addItem(catalog.name, catalog.catalogId)
        self.catalogBox.currentIndexChanged.connect(lambda _: self._onCatalog())
        self.catalogAbout = MutedLabel("")
        self.catalogAbout.setWordWrap(True)
        self.collectionBox = QComboBox()
        self.collectionBox.currentIndexChanged.connect(lambda _: self._onCollection())
        self.addFileButton = QPushButton("Add Footprint File…")
        self.addFileButton.clicked.connect(self._addFootprintFile)
        self.filters = QWidget()
        self.filters.setLayout(QVBoxLayout())
        self.filters.layout().setContentsMargins(0, 0, 0, 0)
        self.areaBox = QComboBox()
        self.areaBox.addItems([AREA_VIEW, AREA_BOX, AREA_IMAGE])
        self.areaBox.currentIndexChanged.connect(lambda _: self._onArea())
        self.areaImage = QComboBox()
        self.fromCheck, self.toCheck = QCheckBox("From"), QCheckBox("To")
        self.fromDate, self.toDate = (
            QDateEdit(QDate(2000, 1, 1)),
            QDateEdit(QDate.currentDate()),
        )
        for check, edit in (
            (self.fromCheck, self.fromDate),
            (self.toCheck, self.toDate),
        ):
            edit.setCalendarPopup(True)
            edit.setDisplayFormat("yyyy-MM-dd")
            edit.setEnabled(False)
            check.toggled.connect(edit.setEnabled)
        self.limit = QSpinBox()
        self.limit.setRange(1, 1000)
        self.limit.setValue(DEFAULT_LIMIT)
        self.searchButton = QPushButton("Search")
        self.searchButton.setDefault(True)
        self.searchButton.clicked.connect(self.search)
        self.moreButton = QPushButton("More Results")
        self.moreButton.clicked.connect(self.more)
        self.moreButton.setEnabled(False)
        self.searchStatus = MutedLabel("")
        self.searchStatus.setWordWrap(True)

        form = QFormLayout()
        form.addRow("Catalog:", self.catalogBox)
        form.addRow("", self.catalogAbout)
        form.addRow("Collection:", self.collectionBox)
        form.addRow("", self.addFileButton)
        form.addRow("Area:", self.areaBox)
        form.addRow("Image:", self.areaImage)
        dates = QHBoxLayout()
        for widget in (self.fromCheck, self.fromDate, self.toCheck, self.toDate):
            dates.addWidget(widget)
        form.addRow("Dates:", dates)
        form.addRow("At most:", self.limit)
        buttons = QHBoxLayout()
        buttons.addWidget(self.searchButton)
        buttons.addWidget(self.moreButton)
        buttons.addStretch()
        self.searchPanel = QWidget()
        layout = QVBoxLayout(self.searchPanel)
        layout.addLayout(form)
        layout.addWidget(QLabel("<b>Filters</b>"))
        layout.addWidget(self.filters)
        layout.addLayout(buttons)
        layout.addWidget(self.searchStatus)
        layout.addStretch(1)

    def _buildMapBar(self) -> None:
        self.bodyLabel = QLabel()
        self.basemapBox = QComboBox()
        self.basemapBox.setToolTip(
            "A loaded, georeferenced image of the same body under the footprints"
        )
        self.basemapBox.currentIndexChanged.connect(lambda _: self._onBasemap())
        overlay = QPushButton("Add Overlay…")
        overlay.setToolTip(
            "A vector file (GeoJSON, shapefile, GeoPackage): a traverse, a geologic map, …"
        )
        overlay.clicked.connect(self._chooseOverlay)
        clear = QPushButton("Clear Overlays")
        clear.clicked.connect(self._clearOverlays)
        whole = QPushButton("Whole Body")
        whole.clicked.connect(self.map.showWhole)
        bar = QHBoxLayout()
        bar.addWidget(self.bodyLabel)
        bar.addWidget(QLabel("Basemap:"))
        bar.addWidget(self.basemapBox, 1)
        bar.addWidget(overlay)
        bar.addWidget(clear)
        bar.addWidget(whole)
        self.mapPanel = QWidget()
        layout = QVBoxLayout(self.mapPanel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(bar)
        layout.addWidget(self.map, 1)

    def _buildPreview(self) -> None:
        self.thumbnail = QLabel("Select a product to see it here.")
        self.thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail.setMinimumSize(220, 220)
        self.details = QLabel()
        self.details.setWordWrap(True)
        self.details.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.details.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.previewPanel = QWidget()
        layout = QVBoxLayout(self.previewPanel)
        layout.addWidget(self.thumbnail)
        layout.addWidget(self.details, 1)

    def _buildDocks(self) -> None:
        self.dockManager = ads.CDockManager(self)
        mapDock = VardaDockWidget("Map").withWidget(self.mapPanel)
        manager = self.dockManager
        manager.addDockWidget(ads.DockWidgetArea.CenterDockWidgetArea, mapDock)
        manager.addDockWidget(
            ads.DockWidgetArea.LeftDockWidgetArea,
            VardaDockWidget("Search").withWidget(self.searchPanel),
            mapDock.dockAreaWidget(),
        )
        manager.addDockWidget(
            ads.DockWidgetArea.RightDockWidgetArea,
            VardaDockWidget("Preview").withWidget(self.previewPanel),
            mapDock.dockAreaWidget(),
        )
        self.resultsDock = VardaDockWidget("Results").withWidget(self.table)
        manager.addDockWidget(
            ads.DockWidgetArea.BottomDockWidgetArea,
            self.resultsDock,
            mapDock.dockAreaWidget(),
        )

    # --- catalogs and collections ----------------------------------------------------------

    def catalog(self) -> Catalog:
        catalogId = self.catalogBox.currentData()
        if catalogId not in self._catalogs:
            cls = next(c for c in availableCatalogs() if c.catalogId == catalogId)
            catalog = self._catalogs[catalogId] = cls()
            if isinstance(catalog, FootprintFileCatalog):
                # the body the user picks changes the collections' map
                catalog.body.sigParameterChanged.connect(
                    lambda _: self._onCatalog(
                        select=self.collectionBox.currentData() or ""
                    )
                )
        return self._catalogs[catalogId]

    def collection(self) -> Collection | None:
        index = self.collectionBox.currentIndex()
        return self._collections[index] if 0 <= index < len(self._collections) else None

    def body(self) -> str:
        collection = self.collection()
        return collection.body if collection is not None else ""

    def _onCatalog(self, select: str = "") -> None:
        if self.catalogBox.count() == 0:
            return
        catalog = self.catalog()
        self.catalogAbout.setText(catalog.description)
        self.addFileButton.setVisible(isinstance(catalog, FootprintFileCatalog))
        layout = self.filters.layout()
        while layout.count():
            item = layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        if catalog.params:
            layout.addWidget(groupWidget(catalog))
        else:
            layout.addWidget(MutedLabel("This catalog has no filters."))
        self.collectionBox.clear()
        self._collections = []
        self.searchStatus.setText("Loading collections…")
        runInBackground(
            catalog.collections,
            lambda collections: self._showCollections(catalog, collections, select),
            lambda error: self.searchStatus.setText(str(error)),
            description="Listing a catalog's collections",
        )

    def _showCollections(
        self, catalog: Catalog, collections: list[Collection], select: str
    ) -> None:
        if catalog is not self.catalog():
            return  # the user moved on
        self._collections = list(collections)
        self.collectionBox.blockSignals(True)
        self.collectionBox.clear()
        for c in self._collections:
            self.collectionBox.addItem(f"{c.body}: {c.title}", c.id)
            self.collectionBox.setItemData(
                self.collectionBox.count() - 1,
                c.description,
                Qt.ItemDataRole.ToolTipRole,
            )
        index = self.collectionBox.findData(select) if select else -1
        self.collectionBox.setCurrentIndex(max(index, 0))
        self.collectionBox.blockSignals(False)
        self.searchStatus.setText(
            f"{len(collections)} collections."
            if collections
            else "This catalog has no collections yet."
        )
        self._onCollection()

    def _onCollection(self) -> None:
        body = self.body()
        self.bodyLabel.setText(f"<b>{body}</b>" if body else "")
        images = [i for i in self.projectImages if imageBody(i) == body] if body else []
        for box in (self.basemapBox, self.areaImage):
            box.blockSignals(True)
            box.clear()
        self.basemapBox.addItem("None", None)
        for image in images:
            self.basemapBox.addItem(image.name, image)
            self.areaImage.addItem(image.name, image)
        for box in (self.basemapBox, self.areaImage):
            box.blockSignals(False)
        self._onArea()
        self._onBasemap()

    def _addFootprintFile(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Add Footprint File",
            "",
            "Vector files (*.shp *.geojson *.json *.gpkg *.kml *.fgb);;All files (*)",
        )
        if path:
            self.addFootprintFile(path)

    def addFootprintFile(self, path: str) -> None:
        if path not in FootprintFileCatalog.paths:
            FootprintFileCatalog.paths.append(path)
        self._onCatalog(select=path)

    # --- search -------------------------------------------------------------------------

    def _onArea(self) -> None:
        mode = self.areaBox.currentText()
        self.map.showArea(mode == AREA_BOX)
        self.areaImage.setEnabled(mode == AREA_IMAGE and self.areaImage.count() > 0)

    def searchArea(self) -> tuple[float, float, float, float] | None:
        mode = self.areaBox.currentText()
        if mode == AREA_BOX:
            return self.map.areaBounds()
        if mode == AREA_IMAGE:
            image = self.areaImage.currentData()
            return imageBounds(image, self.body()) if image is not None else None
        return self.map.viewBounds()

    def query(self) -> SearchQuery | None:
        collection = self.collection()
        if collection is None:
            return None

        def moment(check: QCheckBox, edit: QDateEdit) -> datetime | None:
            if not check.isChecked():
                return None
            date = edit.date()
            return datetime(date.year(), date.month(), date.day(), tzinfo=timezone.utc)

        return SearchQuery(
            collection.id,
            self.searchArea(),
            moment(self.fromCheck, self.fromDate),
            moment(self.toCheck, self.toDate),
            self.limit.value(),
        )

    def search(self) -> None:
        query = self.query()
        if query is None:
            self.searchStatus.setText("Choose a collection first.")
            return
        self._query = query
        self.results.setProducts([])
        self._run(query, append=False)

    def more(self) -> None:
        if self._query is None or self._nextPage is None:
            return
        query = SearchQuery(
            self._query.collection,
            self._query.bbox,
            self._query.start,
            self._query.end,
            self._query.limit,
            self._nextPage,
        )
        self._run(query, append=True)

    def _run(self, query: SearchQuery, append: bool) -> None:
        catalog = self.catalog()
        self.searchButton.setEnabled(False)
        self.moreButton.setEnabled(False)
        self.searchStatus.setText("Searching…")
        runInBackground(
            lambda: catalog.search(query, lambda fraction, message: None),
            lambda page: self._showPage(page, append),
            self._searchFailed,
            description=f"Searching {catalog.name}",
        )

    def _searchFailed(self, error: Exception) -> None:
        self.searchButton.setEnabled(True)
        self.moreButton.setEnabled(self._nextPage is not None)
        self.searchStatus.setText(str(error))

    def _showPage(self, page: SearchPage, append: bool) -> None:
        products = (self.results.products if append else []) + list(page.products)
        self.results.setProducts(products)
        self._nextPage = page.nextPage
        self.map.setFootprints(products)
        self.map.setSelected([])
        self.searchButton.setEnabled(True)
        self.moreButton.setEnabled(page.nextPage is not None)
        total = f" of {page.total}" if page.total is not None else ""
        self.searchStatus.setText(
            f"{len(products)}{total} products." if products else "Nothing found here."
        )
        if products and not append and self.areaBox.currentText() != AREA_VIEW:
            self.map.zoomTo(
                tuple(shapely.union_all([p.footprint for p in products]).bounds)
            )

    # --- selection and preview --------------------------------------------------------------

    def selectedProducts(self) -> list[Product]:
        selection = self.table.selectionModel()
        assert selection is not None
        rows = sorted(
            {self.proxy.mapToSource(i).row() for i in selection.selectedRows()}
        )
        return [self.results.products[r] for r in rows]

    def selectProducts(self, ids: list[str], add: bool = False) -> None:
        selection = self.table.selectionModel()
        assert selection is not None
        if not add:
            selection.clearSelection()
        for row, product in enumerate(self.results.products):
            if product.id in ids:
                index = self.proxy.mapFromSource(self.results.index(row, 1))
                selection.select(
                    index,
                    selection.SelectionFlag.Select | selection.SelectionFlag.Rows,
                )
                self.table.scrollTo(index)

    def _onMapClicked(self, longitude: float, latitude: float, add: bool) -> None:
        point = shapely.Point(longitude, latitude)
        hits = [p.id for p in self.results.products if p.footprint.covers(point)]
        if hits or not add:
            self.selectProducts(hits, add)

    def _onSelection(self) -> None:
        products = self.selectedProducts()
        self.map.setSelected(products)
        if len(products) != 1:
            self.thumbnail.setText(
                "Select one product to see it here." if products else ""
            )
            self.details.setText(
                f"{len(products)} products selected." if products else ""
            )
            return
        product = products[0]
        lines = [f"<b>{product.id}</b>"]
        if product.title != product.id:
            lines.append(product.title)
        if product.start:
            lines.append(f"Start: {product.start:%Y-%m-%d %H:%M:%S}")
        lines += [f"{key}: {value}" for key, value in product.properties.items()]
        self.details.setText("<br>".join(lines))
        self.thumbnail.setText(
            "Loading the thumbnail…" if product.thumbnail else "No thumbnail."
        )
        if product.thumbnail:
            runInBackground(
                lambda: fetchBytes(product.thumbnail),
                lambda data: self._showThumbnail(product, data),
                lambda error: self.thumbnail.setText("No thumbnail."),
                description="Fetching a thumbnail",
            )

    def _showThumbnail(self, product: Product, data: bytes) -> None:
        if self.selectedProducts() != [product]:
            return
        pixmap = QPixmap()
        if not pixmap.loadFromData(data):
            self.thumbnail.setText("No thumbnail.")
            return
        self.thumbnail.setPixmap(
            pixmap.scaled(
                260,
                260,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def _zoomToSelection(self) -> None:
        products = self.selectedProducts()
        if products:
            self.map.zoomTo(
                tuple(shapely.union_all([p.footprint for p in products]).bounds)
            )

    # --- basemap and overlays -----------------------------------------------------------------

    def _onBasemap(self) -> None:
        image = self.basemapBox.currentData()
        if image is None:
            self.map.setBasemap(None)
            return
        body = self.body()
        self.status.showMessage(f"Reprojecting {image.name} for the map…")
        runInBackground(
            lambda: basemap(image, body),
            lambda result: self._showBasemap(*result),
            lambda error: self.status.showMessage(
                f"The basemap couldn't be drawn: {error}", 8000
            ),
            description="Drawing a basemap",
        )

    def _showBasemap(self, rgba, bounds) -> None:
        self.map.setBasemap(rgba, bounds)
        self.status.clearMessage()
        if not self.results.products:
            self.map.zoomTo(bounds, padding=0.05)

    def _chooseOverlay(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Add Overlay",
            "",
            "Vector files (*.shp *.geojson *.json *.gpkg *.kml *.fgb);;All files (*)",
        )
        if path:
            self.addOverlay(path)

    def addOverlay(self, path: str) -> None:
        try:
            frame = gpd.read_file(path)
        except Exception as error:  # pyogrio raises many kinds
            self.status.showMessage(f"Varda couldn't read {path}: {error}", 8000)
            return
        frame = toLongitudeLatitude(frame)
        self.map.addOverlay(list(frame.geometry.dropna()))
        if path not in self.overlayPaths:
            self.overlayPaths.append(path)

    def _clearOverlays(self) -> None:
        self.map.clearOverlays()
        self.overlayPaths = []

    # --- sessions ---------------------------------------------------------------------------

    def sessionState(self) -> dict:
        collection = self.collection()
        return {
            "catalog": self.catalogBox.currentData(),
            "collection": collection.id if collection else "",
            "area": self.areaBox.currentText(),
            "box": list(self.map.areaBounds()),
            "view": list(self.map.viewBounds()),
            "footprintFiles": list(FootprintFileCatalog.paths),
            "overlays": list(self.overlayPaths),
        }

    def restoreSessionState(self, state: dict) -> None:
        for path in state.get("footprintFiles", []):
            if path not in FootprintFileCatalog.paths:
                FootprintFileCatalog.paths.append(path)
        index = self.catalogBox.findData(state.get("catalog"))
        if index >= 0:
            self.catalogBox.blockSignals(True)
            self.catalogBox.setCurrentIndex(index)
            self.catalogBox.blockSignals(False)
        self._onCatalog(select=state.get("collection", ""))
        area = self.areaBox.findText(state.get("area", AREA_VIEW))
        self.areaBox.setCurrentIndex(max(area, 0))
        if state.get("box"):
            self.map.setArea(tuple(state["box"]))
        if state.get("view"):
            self.map.zoomTo(tuple(state["view"]), padding=0)
        for path in state.get("overlays", []):
            self.addOverlay(path)
