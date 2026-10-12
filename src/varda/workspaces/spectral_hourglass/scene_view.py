"""The scene: the image with the hourglass results laid over it.

Overlays (one at a time, with an opacity slider): an MNF component, the PPI
counts, or a band of a map result (class maps in the endmember colours).
Endmember pixels are filled in their class colour, candidate pure pixels can
be ringed, and the pixel hovered in the n-D view is marked.
"""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import QPointF, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.image_rendering.image_renderer import ImageRenderer, RenderMode
from varda.image_rendering.raster_view.image_viewport import ImageViewport
from varda.image_rendering.raster_view.viewport_tools.pixel_select_tool import (
    PixelSelectTool,
)
from varda.image_rendering.raster_view.viewport_tools.tool_manager import ToolManager


class Overlay:
    NONE = "None"
    MNF = "MNF component"
    PPI = "Pixel purity (PPI)"
    MAP = "Map"


def _rasterLike(image: VardaRaster, values: np.ndarray, name: str) -> VardaRaster:
    data = np.asarray(values, dtype=np.float32)
    if data.ndim == 2:
        data = data[:, :, np.newaxis]
    bands = [f"{name} {i + 1}" for i in range(data.shape[2])]
    source = ArrayDataSource(
        data,
        wavelengths=np.array(bands),
        bandNames=bands,
        transform=image.transform,
        crs=image.crs,
        defaultBands=np.arange(min(3, data.shape[2])) if data.shape[2] >= 3 else None,
    )
    return VardaRaster(source, name=name)


def classColorImage(classes: np.ndarray, colors: list[str]) -> np.ndarray:
    """(rows, cols, 3) RGB in 0-1 for a class band (NaN -> black)."""
    rgb = np.zeros(classes.shape + (3,), dtype=np.float32)
    for k, color in enumerate(colors):
        c = pg.mkColor(color)
        rgb[classes == k] = (c.redF(), c.greenF(), c.blueF())
    return rgb


class SceneView(QWidget):
    sigPixelClicked = pyqtSignal(int)  # flat pixel index

    def __init__(self, image: VardaRaster, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.image = image
        self.renderer = ImageRenderer(image=image)
        if image.bandCount >= 3:
            self.renderer.settings.mode.set(RenderMode.RGB)
        self.viewport = ImageViewport(self.renderer, self)
        self.toolManager = ToolManager(self.viewport, self)
        self.viewport.addToolBar(self.toolManager.getToolbar())
        self.toolManager.sigToolActivated.connect(self._onToolActivated)

        self._sources: dict[str, np.ndarray | None] = {}
        self._mapRaster: VardaRaster | None = None
        self._overlayRenderer: ImageRenderer | None = None
        self.componentImage = None  # callable: index -> (rows, cols)

        self.endmemberItem = pg.ScatterPlotItem(
            symbol="s", size=1.0, pxMode=False, pen=None
        )
        self.candidateItem = pg.ScatterPlotItem(
            symbol="o", size=5, pen=pg.mkPen("#ffffffaa", width=1), brush=None
        )
        self.hoverItem = pg.ScatterPlotItem(
            symbol="o", size=16, pen=pg.mkPen("#ffff00", width=2), brush=None
        )
        for item in (self.endmemberItem, self.candidateItem, self.hoverItem):
            item.setZValue(20)
            self.viewport.addItem(item)

        self.overlayBox = QComboBox()
        self.overlayBox.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.overlayBox.addItem(Overlay.NONE)
        self.overlayBox.currentTextChanged.connect(lambda _: self._applyOverlay())
        self.componentSpin = QSpinBox()
        self.componentSpin.setPrefix("MNF ")
        self.componentSpin.setRange(1, 1)
        self.componentSpin.valueChanged.connect(lambda _: self._applyOverlay())
        self.mapBandBox = QComboBox()
        self.mapBandBox.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.mapBandBox.currentIndexChanged.connect(lambda _: self._applyOverlay())
        self.opacitySlider = QSlider(Qt.Orientation.Horizontal)
        self.opacitySlider.setRange(0, 100)
        self.opacitySlider.setValue(70)
        self.opacitySlider.setMinimumWidth(70)
        self.opacitySlider.setMaximumWidth(120)
        self.opacitySlider.valueChanged.connect(self._applyOpacity)
        self.endmembersBox = QCheckBox("Endmember pixels")
        self.endmembersBox.setChecked(True)
        self.endmembersBox.toggled.connect(self.endmemberItem.setVisible)
        self.candidatesBox = QCheckBox("Candidates")
        self.candidatesBox.setToolTip(
            "Ring the candidate pure pixels shown in the n-D view"
        )
        self.candidatesBox.toggled.connect(self.candidateItem.setVisible)
        self.candidateItem.setVisible(False)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Overlay"))
        controls.addWidget(self.overlayBox)
        controls.addWidget(self.componentSpin)
        controls.addWidget(self.mapBandBox)
        controls.addWidget(QLabel("Opacity"))
        controls.addWidget(self.opacitySlider)
        controls.addStretch()
        controls.addWidget(self.endmembersBox)
        controls.addWidget(self.candidatesBox)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(controls)
        layout.addWidget(self.viewport, stretch=1)
        self._syncControls()

    # --- overlays ------------------------------------------------------------------

    def _ensureOverlayOption(self, name: str) -> None:
        if self.overlayBox.findText(name) < 0:
            self.overlayBox.addItem(name)

    def enableComponents(self, count: int, componentImage) -> None:
        """Offer MNF components 1..count; ``componentImage(i)`` gives one."""
        self.componentImage = componentImage
        self.componentSpin.setRange(1, max(1, count))
        self._ensureOverlayOption(Overlay.MNF)
        if self.overlayBox.currentText() == Overlay.MNF:
            self._applyOverlay()

    def setPpi(self, ppi: np.ndarray | None) -> None:
        self._sources[Overlay.PPI] = ppi
        if ppi is not None:
            self._ensureOverlayOption(Overlay.PPI)
        if self.overlayBox.currentText() == Overlay.PPI:
            self._applyOverlay()

    def setMapResult(self, raster: VardaRaster) -> None:
        self._mapRaster = raster
        self.mapBandBox.blockSignals(True)
        self.mapBandBox.clear()
        self.mapBandBox.addItems(list(raster.bandNames))
        self.mapBandBox.blockSignals(False)
        self._ensureOverlayOption(Overlay.MAP)
        self.showOverlay(Overlay.MAP)

    def showOverlay(self, name: str) -> None:
        if self.overlayBox.findText(name) >= 0:
            if self.overlayBox.currentText() == name:
                self._applyOverlay()
            self.overlayBox.setCurrentText(name)

    def currentOverlay(self) -> str:
        return self.overlayBox.currentText()

    def _syncControls(self) -> None:
        overlay = self.overlayBox.currentText()
        self.componentSpin.setVisible(overlay == Overlay.MNF)
        self.mapBandBox.setVisible(overlay == Overlay.MAP)
        self.opacitySlider.setEnabled(overlay != Overlay.NONE)

    def _overlayRaster(
        self,
    ) -> tuple[VardaRaster, bool, tuple[float, float] | None] | None:
        """(raster, isRgb, manual stretch) for the chosen overlay."""
        overlay = self.overlayBox.currentText()
        if overlay == Overlay.MNF and self.componentImage is not None:
            values = self.componentImage(self.componentSpin.value() - 1)
            return _rasterLike(self.image, values, "MNF"), False, None
        if overlay == Overlay.PPI and self._sources.get(Overlay.PPI) is not None:
            ppi = self._sources[Overlay.PPI]
            assert ppi is not None
            positive = ppi[np.isfinite(ppi) & (ppi > 0)]
            top = float(np.percentile(positive, 99)) if positive.size else 1.0
            return _rasterLike(self.image, ppi, "PPI"), False, (0.0, max(top, 1.0))
        if overlay == Overlay.MAP and self._mapRaster is not None:
            raster = self._mapRaster
            band = max(0, self.mapBandBox.currentIndex())
            values = raster.getData()[:, :, band]
            if raster.bandNames[band] == "Class":
                colors = raster.extraMetadata.get("classColors", [])
                return (
                    _rasterLike(self.image, classColorImage(values, colors), "Classes"),
                    True,
                    (0.0, 1.0),
                )
            return _rasterLike(self.image, values, raster.bandNames[band]), False, None
        return None

    def _applyOverlay(self) -> None:
        self._syncControls()
        if self._overlayRenderer is not None:
            self.viewport.removeOverlayImage()
            self._overlayRenderer = None
        chosen = self._overlayRaster()
        if chosen is None:
            self.viewport.refresh()
            return
        raster, isRgb, stretch = chosen
        renderer = ImageRenderer(image=raster)
        if isRgb:
            renderer.settings.mode.set(RenderMode.RGB)
        else:
            renderer.settings.mono.colorMap.set(pg.colormap.get("inferno"))
        if stretch is not None:
            renderer.setManualStretch(*stretch)
        renderer.settings.opacity.set(self.opacitySlider.value() / 100.0)
        self._overlayRenderer = renderer
        self.viewport.overlayImage(renderer)
        self.viewport.refresh()

    def _applyOpacity(self, value: int) -> None:
        if self._overlayRenderer is not None:
            self._overlayRenderer.settings.opacity.set(value / 100.0)

    # --- markers --------------------------------------------------------------------

    def _centres(self, pixels: np.ndarray) -> np.ndarray:
        rows, cols = np.unravel_index(
            np.asarray(pixels, dtype=np.int64), (self.image.height, self.image.width)
        )
        return np.column_stack([cols + 0.5, rows + 0.5]).astype(float)

    def setEndmemberPixels(self, groups: list[tuple[np.ndarray, str]]) -> None:
        """(flat pixels, colour) per endmember."""
        positions, brushes = [], []
        for pixels, color in groups:
            if len(pixels):
                positions.append(self._centres(pixels))
                brushes += [pg.mkBrush(color)] * len(pixels)
        if positions:
            self.endmemberItem.setData(pos=np.vstack(positions), brush=brushes)
        else:
            self.endmemberItem.setData([], [])

    def setCandidatePixels(self, pixels: np.ndarray) -> None:
        if len(pixels):
            self.candidateItem.setData(pos=self._centres(pixels))
        else:
            self.candidateItem.setData([], [])

    def highlightPixel(self, pixel: int | None) -> None:
        if pixel is None:
            self.hoverItem.setData([], [])
        else:
            self.hoverItem.setData(pos=self._centres(np.array([pixel])))

    # --- tools -----------------------------------------------------------------------

    def _onToolActivated(self, tool) -> None:
        if isinstance(tool, PixelSelectTool):
            tool.sigPixelSelected.connect(self._onPixelSelected)

    def _onPixelSelected(self, pos: QPointF) -> None:
        col, row = int(pos.x()), int(pos.y())
        if 0 <= row < self.image.height and 0 <= col < self.image.width:
            self.sigPixelClicked.emit(row * self.image.width + col)
