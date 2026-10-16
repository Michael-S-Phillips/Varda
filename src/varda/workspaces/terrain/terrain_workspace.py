"""The 3D Terrain workspace: a DEM as a lit, shadowed surface, with shaded
relief, elevation colors or an image on its grid draped over it; vertical
exaggeration, the sun's direction, saved camera views, high-resolution
stills, and a self-contained web page to share."""

from __future__ import annotations

from collections.abc import MutableSequence

import numpy as np
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from varda.common.entities import VardaRaster
from varda.common.grid import compatibleImages
from varda.common.observable_list import ObservableList
from varda.common.ui import MutedLabel
from varda.image_rendering.image_renderer import ImageRenderer, RenderMode
from varda.image_rendering.render_parameters import StretchParameter
from varda.image_rendering.stretch_algorithms import LinearPercentileStretch
from varda.terrain.scene import (
    Terrain,
    TerrainSettings,
    buildTerrain,
    groundSize,
    pageHtml,
    pngDataUrl,
)
from varda.utilities.background import runInBackground
from varda.workspaces.raster_overlay import COLOR_MAPS, colorMap
from varda.workspaces.terrain.terrain_view import TerrainView

PLAIN, ELEVATION = "None (shaded relief)", "Elevation colors"
DETAIL = {"Low": 512, "Medium": 1024, "High": 2048}
BACKGROUNDS = {"Dark": "#101418", "Black": "#000000", "White": "#ffffff"}
STILL_SIZES = {
    "HD (1920 × 1080)": (1920, 1080),
    "4K (3840 × 2160)": (3840, 2160),
    "8K (7680 × 4320)": (7680, 4320),
    "Square (3000 × 3000)": (3000, 3000),
}
MAX_STILL = 16384  # px on a side: WebGL's canvas limit


def drapeRgba(image: VardaRaster, elevation: str | None = None) -> np.ndarray:
    """An image as RGBA (no data transparent): its usual rendering, or for
    ``elevation`` (a color map name) its first band through that map,
    stretched 2-98 %."""
    renderer = ImageRenderer(image=image)
    renderer.transparentNoData = True
    settings = renderer.settings
    with settings.sigParameterChanged.blocked():
        if elevation is not None:
            settings.mode.set(RenderMode.MONO)
            settings.mono.band.set(0)
            settings.mono.colorMap.set(colorMap(elevation))
        elif image.bandCount >= 3:
            settings.mode.set(RenderMode.RGB)
        percentile = settings.stretch.option("Linear Percentile")
        assert isinstance(percentile, LinearPercentileStretch)
        percentile.config.lowPercent.set(2)
        percentile.config.highPercent.set(98)
        settings.stretch.selectByName("Linear Percentile")
    rgba = np.asarray(renderer.render())
    settings.stretch.selectByName(StretchParameter.DEFAULT_NAME)  # leave no trace
    return rgba


class StillDialog(QDialog):
    """The size of a still and whether its background is transparent."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Export Still")
        self.preset = QComboBox()
        self.preset.addItems([*STILL_SIZES, "Custom"])
        self.preset.setCurrentText("4K (3840 × 2160)")
        self.widthBox = QSpinBox()
        self.heightBox = QSpinBox()
        for box in (self.widthBox, self.heightBox):
            box.setRange(64, MAX_STILL)
            box.setSuffix(" px")
        self.transparent = QCheckBox("Transparent background")
        self.preset.currentTextChanged.connect(self._onPreset)
        self._onPreset(self.preset.currentText())
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form = QFormLayout(self)
        form.addRow("Size:", self.preset)
        form.addRow("Width:", self.widthBox)
        form.addRow("Height:", self.heightBox)
        form.addRow("", self.transparent)
        form.addRow(buttons)

    def _onPreset(self, name: str) -> None:
        size = STILL_SIZES.get(name)
        for box in (self.widthBox, self.heightBox):
            box.setEnabled(size is None)
        if size is not None:
            self.widthBox.setValue(size[0])
            self.heightBox.setValue(size[1])

    def stillSize(self) -> tuple[int, int]:
        return self.widthBox.value(), self.heightBox.value()


class TerrainWorkspace(QMainWindow):
    def __init__(
        self,
        projectImages: MutableSequence[VardaRaster],
        dem: VardaRaster | None = None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("3D Terrain")
        self.projectImages = projectImages
        self.settings = TerrainSettings()
        self.terrain: Terrain | None = None
        self.views: dict[str, dict] = {}  # name -> camera
        self._camera: dict | None = None  # kept across page rebuilds
        self._building = 0  # the latest build (older results are dropped)
        self._restoring = False

        self.view = TerrainView()
        self.view.sigReady.connect(self._onReady)
        self.view.sigFailed.connect(self._onFailed)
        self._buildPanel()
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.panel)
        splitter.addWidget(self.view)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([320, 1100])
        self.setCentralWidget(splitter)

        self._refreshImages(select=dem)
        if isinstance(projectImages, ObservableList):
            projectImages.sigDataChanged.connect(lambda _: self._refreshImages())

    # --- the panel ------------------------------------------------------------------

    def _buildPanel(self) -> None:
        self.demBox = QComboBox()
        self.demBox.setToolTip("The elevation image (a DEM)")
        self.demBox.currentIndexChanged.connect(lambda _: self._onDem())
        self.bandBox = QComboBox()
        self.bandBox.currentIndexChanged.connect(lambda _: self.rebuild())
        self.drapeBox = QComboBox()
        self.drapeBox.setToolTip(
            "What covers the surface: plain shaded relief, the elevations "
            "colored, or a loaded image on the DEM's grid (e.g. its orthoimage)"
        )
        self.drapeBox.currentIndexChanged.connect(lambda _: self._onDrape())
        self.colorMapBox = QComboBox()
        self.colorMapBox.addItems(list(COLOR_MAPS))
        self.colorMapBox.currentIndexChanged.connect(lambda _: self.rebuild())
        self.detailBox = QComboBox()
        self.detailBox.addItems(list(DETAIL))
        self.detailBox.setCurrentText("Medium")
        self.detailBox.setToolTip("How finely the surface follows the DEM")
        self.detailBox.currentIndexChanged.connect(lambda _: self.rebuild())

        self.exaggeration = QDoubleSpinBox()
        self.exaggeration.setRange(0.1, 50)
        self.exaggeration.setSingleStep(0.5)
        self.exaggeration.setSuffix(" ×")
        self.sunAzimuth = QSpinBox()
        self.sunAzimuth.setRange(0, 359)
        self.sunAzimuth.setWrapping(True)
        self.sunAzimuth.setSuffix("°")
        self.sunAzimuth.setToolTip("Clockwise from north")
        self.sunElevation = QSpinBox()
        self.sunElevation.setRange(1, 90)
        self.sunElevation.setSuffix("°")
        self.shadows = QCheckBox("Cast shadows")
        self.ambient = QDoubleSpinBox()
        self.ambient.setRange(0, 1.5)
        self.ambient.setSingleStep(0.05)
        self.ambient.setToolTip("Light from the sky, which lifts the shadows")
        self.background = QComboBox()
        self.background.addItems(list(BACKGROUNDS))
        self._showSettings()
        for box in (self.exaggeration, self.ambient):
            box.valueChanged.connect(lambda _: self._onSettings())
        for box in (self.sunAzimuth, self.sunElevation):
            box.valueChanged.connect(lambda _: self._onSettings())
        self.shadows.toggled.connect(lambda _: self._onSettings())
        self.background.currentIndexChanged.connect(lambda _: self._onSettings())

        self.viewList = QListWidget()
        self.viewList.setToolTip("Saved camera views; double-click one to go to it")
        self.viewList.itemDoubleClicked.connect(self._goToView)
        saveView = QPushButton("Save View…")
        saveView.clicked.connect(self._saveView)
        deleteView = QPushButton("Delete")
        deleteView.clicked.connect(self._deleteView)
        home = QPushButton("Reset View")
        home.clicked.connect(self.view.home)
        still = QPushButton("Export Still…")
        still.setToolTip("Render the view as a high-resolution PNG for a figure")
        still.clicked.connect(self.exportStill)
        web = QPushButton("Export Web Page…")
        web.setToolTip(
            "Save an interactive 3D page that opens in any web browser, to share "
            "or to publish with a paper"
        )
        web.clicked.connect(self.exportWebPage)

        self.form = form = QFormLayout()
        form.addRow("DEM:", self.demBox)
        form.addRow("Band:", self.bandBox)
        form.addRow("Drape:", self.drapeBox)
        form.addRow("Color map:", self.colorMapBox)
        form.addRow("Detail:", self.detailBox)
        form.addRow("Exaggeration:", self.exaggeration)
        form.addRow("Sun azimuth:", self.sunAzimuth)
        form.addRow("Sun elevation:", self.sunElevation)
        form.addRow("", self.shadows)
        form.addRow("Sky light:", self.ambient)
        form.addRow("Background:", self.background)
        viewButtons = QHBoxLayout()
        for button in (saveView, deleteView, home):
            viewButtons.addWidget(button)
        exports = QHBoxLayout()
        exports.addWidget(still)
        exports.addWidget(web)
        self.status = MutedLabel("")
        self.status.setWordWrap(True)
        self.panel = QWidget()
        layout = QVBoxLayout(self.panel)
        layout.addLayout(form)
        layout.addWidget(QLabel("<b>Views</b>"))
        layout.addWidget(self.viewList, 1)
        layout.addLayout(viewButtons)
        layout.addLayout(exports)
        layout.addWidget(self.status)

    def dem(self) -> VardaRaster | None:
        return self.demBox.currentData()

    def drapeImage(self) -> VardaRaster | None:
        data = self.drapeBox.currentData()
        return data if isinstance(data, VardaRaster) else None

    def _refreshImages(self, select: VardaRaster | None = None) -> None:
        current = select or self.dem()
        self.demBox.blockSignals(True)
        self.demBox.clear()
        for image in self.projectImages:
            self.demBox.addItem(image.name, image)
        index = next(
            (
                i
                for i in range(self.demBox.count())
                if self.demBox.itemData(i) is current
            ),
            -1,
        )
        if index < 0:  # a single-band image is most likely the DEM
            index = next(
                (
                    i
                    for i, image in enumerate(self.projectImages)
                    if image.bandCount == 1
                ),
                0,
            )
        self.demBox.setCurrentIndex(index)
        self.demBox.blockSignals(False)
        if self.dem() is not current or select is not None:
            self._onDem()
        else:
            self._refreshDrapes()

    def _onDem(self) -> None:
        dem = self.dem()
        self.bandBox.blockSignals(True)
        self.bandBox.clear()
        if dem is not None:
            names = list(dem.bandNames or [])
            for band in range(dem.bandCount):
                self.bandBox.addItem(
                    names[band] if band < len(names) else f"Band {band + 1}", band
                )
        self.form.setRowVisible(self.bandBox, dem is not None and dem.bandCount > 1)
        self.bandBox.blockSignals(False)
        self._refreshDrapes()
        self.rebuild()

    def _refreshDrapes(self) -> None:
        dem = self.dem()
        current = self.drapeBox.currentData()
        self.drapeBox.blockSignals(True)
        self.drapeBox.clear()
        self.drapeBox.addItem(PLAIN, PLAIN)
        self.drapeBox.addItem(ELEVATION, ELEVATION)
        if dem is not None:
            for image in compatibleImages(list(self.projectImages), dem):
                self.drapeBox.addItem(image.name, image)
        index = next(
            (
                i
                for i in range(self.drapeBox.count())
                if self.drapeBox.itemData(i) is current
            ),
            1,
        )
        self.drapeBox.setCurrentIndex(index)
        self.drapeBox.blockSignals(False)
        self.form.setRowVisible(
            self.colorMapBox, self.drapeBox.currentData() == ELEVATION
        )

    def _onDrape(self) -> None:
        self.form.setRowVisible(
            self.colorMapBox, self.drapeBox.currentData() == ELEVATION
        )
        self.rebuild()

    # --- settings ----------------------------------------------------------------------

    def _showSettings(self) -> None:
        widgets = (
            self.exaggeration,
            self.sunAzimuth,
            self.sunElevation,
            self.shadows,
            self.ambient,
            self.background,
        )
        for widget in widgets:
            widget.blockSignals(True)
        self.exaggeration.setValue(self.settings.exaggeration)
        self.sunAzimuth.setValue(int(self.settings.sunAzimuth) % 360)
        self.sunElevation.setValue(int(self.settings.sunElevation))
        self.shadows.setChecked(self.settings.shadows)
        self.ambient.setValue(self.settings.ambient)
        name = next(
            (n for n, c in BACKGROUNDS.items() if c == self.settings.background), "Dark"
        )
        self.background.setCurrentText(name)
        for widget in widgets:
            widget.blockSignals(False)

    def _onSettings(self) -> None:
        self.settings = TerrainSettings(
            exaggeration=self.exaggeration.value(),
            sunAzimuth=self.sunAzimuth.value(),
            sunElevation=self.sunElevation.value(),
            shadows=self.shadows.isChecked(),
            background=BACKGROUNDS[self.background.currentText()],
            ambient=self.ambient.value(),
        )
        self.view.setSettings(self.settings.toDict())

    # --- building the page ---------------------------------------------------------------

    def rebuild(self) -> None:
        """Build the page again for the DEM, band, drape or detail (keeping
        the camera); settings alone don't need this."""
        dem = self.dem()
        if dem is None or self._restoring:
            return
        if self.view.ready:  # keep where the camera is
            self.view.camera(lambda camera: self._build(dem, camera))
        else:
            self._build(dem, self._camera)

    def _build(self, dem: VardaRaster, camera: dict | None) -> None:
        self._camera = camera or self._camera
        self._building += 1
        build = self._building
        band = int(self.bandBox.currentData() or 0)
        drape = self.drapeBox.currentData()
        try:  # rendering the drape uses Qt-side objects: here, on the GUI thread
            rgba = (
                None
                if drape == PLAIN
                else drapeRgba(dem, self.colorMapBox.currentText())
                if drape == ELEVATION
                else drapeRgba(drape)
            )
        except Exception as error:  # a broken image shouldn't break the workspace
            self.status.setText(f"The drape couldn't be drawn: {error}")
            rgba = None
        maxSide = DETAIL[self.detailBox.currentText()]
        settings, title = self.settings, dem.name
        size = groundSize(dem)  # pyproj, so here: its objects aren't thread-safe
        self.status.setText("Building the surface…")

        def work() -> tuple[Terrain, str]:
            terrain = buildTerrain(dem, band, maxSide, size)
            texture = None if rgba is None else pngDataUrl(rgba)
            return terrain, pageHtml(terrain, texture, settings, self._camera, title)

        runInBackground(
            work,
            lambda result: self._show(build, *result),
            lambda error: self.status.setText(
                f"The surface couldn't be built: {error}"
            ),
            description="Building a 3D surface",
            owner=self,
        )

    def _show(self, build: int, terrain: Terrain, html: str) -> None:
        if build != self._building:
            return  # a newer build is on its way
        self.terrain = terrain
        self.view.showPage(html)

    def _onReady(self) -> None:
        if self.terrain is None:
            return
        low, high = self.terrain.zRange
        rows, cols = self.terrain.heights.shape
        self.status.setText(
            f"{self.terrain.widthM / 1000:.3g} × {self.terrain.heightM / 1000:.3g} km, "
            f"heights {low:.0f} to {high:.0f}; a {cols} × {rows} grid"
            + (f" (every {self.terrain.step} pixels)" if self.terrain.step > 1 else "")
        )
        self.view.setSettings(self.settings.toDict())  # changed while it loaded

    def _onFailed(self, reason: str) -> None:
        self.status.setText(
            "The 3D view needs WebGL 2, which this computer's graphics don't "
            f"offer ({reason}). Updating the graphics driver may help."
        )

    # --- views ------------------------------------------------------------------------

    def _saveView(self) -> None:
        name, ok = QInputDialog.getText(
            self, "Save View", "Name:", text=f"View {len(self.views) + 1}"
        )
        if ok and name:
            self.view.camera(lambda camera: self._keepView(name, camera))

    def _keepView(self, name: str, camera: dict | None) -> None:
        if camera is None:
            return
        if name not in self.views:
            self.viewList.addItem(QListWidgetItem(name))
        self.views[name] = camera

    def _goToView(self, item: QListWidgetItem) -> None:
        camera = self.views.get(item.text())
        if camera is not None:
            self.view.setCamera(camera)

    def _deleteView(self) -> None:
        for item in self.viewList.selectedItems():
            self.views.pop(item.text(), None)
            self.viewList.takeItem(self.viewList.row(item))

    # --- exports ---------------------------------------------------------------------

    def exportStill(self) -> None:
        if not self.view.ready:
            return
        dialog = StillDialog(self)
        if not dialog.exec():
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Still", f"{self.windowTitle()}.png", "PNG image (*.png)"
        )
        if path:
            self.saveStill(path, *dialog.stillSize(), dialog.transparent.isChecked())

    def saveStill(self, path: str, width: int, height: int, transparent: bool) -> None:
        self.status.setText("Rendering the still…")

        def done(png: bytes | None) -> None:
            if png is None:
                self.status.setText("The still couldn't be rendered.")
                return
            with open(path, "wb") as f:
                f.write(png)
            self.status.setText(f"Saved a {width} × {height} still to {path}.")

        self.view.still(width, height, transparent, done)

    def exportWebPage(self) -> None:
        if self.terrain is None:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Web Page", f"{self.windowTitle()}.html", "Web page (*.html)"
        )
        if path:
            self.view.camera(lambda camera: self.saveWebPage(path, camera))

    def saveWebPage(self, path: str, camera: dict | None) -> None:
        """The view as a self-contained page with controls for its readers."""
        terrain = self.terrain
        if terrain is None:
            return
        dem = self.dem()
        title = dem.name if dem is not None else "Varda 3D view"
        # the shown page has no reader controls and may predate the camera
        drape = self.drapeBox.currentData()
        rgba = (
            None
            if drape == PLAIN
            else drapeRgba(dem, self.colorMapBox.currentText())
            if drape == ELEVATION and dem is not None
            else drapeRgba(drape)
            if isinstance(drape, VardaRaster)
            else None
        )
        texture = None if rgba is None else pngDataUrl(rgba)
        html = pageHtml(terrain, texture, self.settings, camera, title, panel=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        self.status.setText(f"Saved an interactive web page to {path}.")

    # --- sessions ------------------------------------------------------------------------

    def sessionState(self) -> dict:
        drape = self.drapeBox.currentData()
        return {
            "band": int(self.bandBox.currentData() or 0),
            "drape": drape if isinstance(drape, str) else "image",
            "colorMap": self.colorMapBox.currentText(),
            "detail": self.detailBox.currentText(),
            "settings": self.settings.toDict(),
            "views": dict(self.views),
            "camera": self._camera,
        }

    def restoreSessionState(
        self, state: dict, drape: VardaRaster | None = None
    ) -> None:
        self._restoring = True
        try:
            self.settings = TerrainSettings.fromDict(state.get("settings", {}))
            self._showSettings()
            index = self.bandBox.findData(state.get("band", 0))
            self.bandBox.setCurrentIndex(max(index, 0))
            self.colorMapBox.setCurrentText(state.get("colorMap", "Viridis"))
            self.detailBox.setCurrentText(state.get("detail", "Medium"))
            choice = state.get("drape", ELEVATION)
            target = drape if choice == "image" else choice
            for i in range(self.drapeBox.count()):
                if (
                    self.drapeBox.itemData(i) == target
                    or self.drapeBox.itemData(i) is target
                ):
                    self.drapeBox.setCurrentIndex(i)
            self.form.setRowVisible(
                self.colorMapBox, self.drapeBox.currentData() == ELEVATION
            )
            for name, camera in state.get("views", {}).items():
                self._keepView(name, camera)
            self._camera = state.get("camera")
        finally:
            self._restoring = False
        self.rebuild()
