"""Overlay a co-registered project image on a workspace's views.

Any project image on the same pixel grid as the workspace's image can be laid
over it: a classification shows its classes in their colours (or one class's
probability), any other result one band through a colour map. Pixels without
data stay see-through. The bar sits under the main view and drives every view
it is given (the triple view's zoom panels follow the main view).
"""

from __future__ import annotations

from collections.abc import Sequence
from html import escape

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QSlider, QWidget

from varda.common.entities import VardaRaster
from varda.common.observable_list import ObservableList
from varda.common.palette import classColor
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.image_rendering.image_renderer import ImageRenderer, RenderMode
from varda.image_rendering.raster_view.image_viewport import ImageViewport

NO_OVERLAY = "No overlay"
CLASSES = "Classes"
COLOR_MAP = "viridis"


def _sameGrid(a: VardaRaster, b: VardaRaster) -> bool:
    if (a.height, a.width) != (b.height, b.width):
        return False
    if a.hasGeospatialData and b.hasGeospatialData:
        return a.crs == b.crs and a.transform.almost_equals(b.transform)
    return a.hasGeospatialData == b.hasGeospatialData


def compatibleImages(
    images: Sequence[VardaRaster], base: VardaRaster
) -> list[VardaRaster]:
    """The images that can be laid over ``base``: same pixel grid, not itself."""
    return [image for image in images if image is not base and _sameGrid(image, base)]


def isClassMap(raster: VardaRaster) -> bool:
    return bool(raster.bandNames) and raster.bandNames[0] == "Class"


def overlayLayers(raster: VardaRaster) -> list[str]:
    names = list(raster.bandNames)
    return [CLASSES, *names[1:]] if isClassMap(raster) else names


def classColors(raster: VardaRaster) -> list[str]:
    names = raster.extraMetadata.get("classes", [])
    stored = list(raster.extraMetadata.get("classColors", []))
    return stored + [classColor(k) for k in range(len(stored), len(names))]


def _like(raster: VardaRaster, data: np.ndarray, name: str) -> VardaRaster:
    bands = [f"{name} {i + 1}" for i in range(data.shape[2])]
    source = ArrayDataSource(
        data.astype(np.float32),
        bandNames=bands,
        transform=raster.transform,
        crs=raster.crs,
        defaultBands=np.arange(3) if data.shape[2] == 3 else None,
    )
    return VardaRaster(source, name=name)


def overlayRaster(raster: VardaRaster, layer: str) -> tuple[VardaRaster, bool]:
    """(image to render, whether it is RGB) for one layer of ``raster``."""
    if layer == CLASSES:
        classes = raster.getData()[:, :, 0]
        rgb = np.full(classes.shape + (3,), np.nan, dtype=np.float32)
        for k, color in enumerate(classColors(raster)):
            c = pg.mkColor(color)
            rgb[classes == k] = (c.redF(), c.greenF(), c.blueF())
        return _like(raster, rgb, CLASSES), True
    band = list(raster.bandNames).index(layer)
    return _like(raster, raster.getData()[:, :, band : band + 1], layer), False


class OverlayBar(QWidget):
    """Overlay picker, layer picker, opacity and (for class maps) a legend."""

    def __init__(
        self,
        images: Sequence[VardaRaster],
        base: VardaRaster,
        viewports: Sequence[ImageViewport],
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self.images = images
        self.base = base
        self.viewports = list(viewports)
        self.renderer: ImageRenderer | None = None
        self._candidates: list[VardaRaster] = []

        self.imageBox = QComboBox()
        self.imageBox.setToolTip(
            "Lay another image of this scene (e.g. a classification) over the view"
        )
        self.imageBox.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.layerBox = QComboBox()
        self.opacitySlider = QSlider(Qt.Orientation.Horizontal)
        self.opacitySlider.setRange(0, 100)
        self.opacitySlider.setValue(60)
        self.opacitySlider.setMaximumWidth(120)
        self.opacitySlider.setToolTip("Overlay opacity")
        self.legend = QLabel()
        self.legend.setTextFormat(Qt.TextFormat.RichText)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.addWidget(QLabel("Overlay:"))
        layout.addWidget(self.imageBox)
        layout.addWidget(self.layerBox)
        layout.addWidget(QLabel("Opacity:"))
        layout.addWidget(self.opacitySlider)
        layout.addWidget(self.legend, 1)

        self.imageBox.currentIndexChanged.connect(self._onImageChosen)
        self.layerBox.currentIndexChanged.connect(lambda _: self._apply())
        self.opacitySlider.valueChanged.connect(self._applyOpacity)
        if isinstance(images, ObservableList):
            images.sigDataChanged.connect(lambda _: self._refreshImages())
        self._refreshImages()

    # --- public ----------------------------------------------------------------

    def currentOverlay(self) -> VardaRaster | None:
        index = self.imageBox.currentIndex()
        return self._candidates[index - 1] if index > 0 else None

    def setOverlay(self, image: VardaRaster | None) -> None:
        index = 0 if image is None else 1 + self._candidates.index(image)
        self.imageBox.setCurrentIndex(index)

    # --- internals -------------------------------------------------------------

    def _refreshImages(self) -> None:
        current = self.currentOverlay()
        self._candidates = compatibleImages(list(self.images), self.base)
        self.imageBox.blockSignals(True)
        self.imageBox.clear()
        self.imageBox.addItem(NO_OVERLAY)
        for image in self._candidates:
            self.imageBox.addItem(image.name)
        self.imageBox.blockSignals(False)
        if current in self._candidates:
            self.setOverlay(current)
        else:
            self.imageBox.setCurrentIndex(0)
            self._onImageChosen()

    def _onImageChosen(self, *_args) -> None:
        overlay = self.currentOverlay()
        self.layerBox.blockSignals(True)
        self.layerBox.clear()
        if overlay is not None:
            self.layerBox.addItems(overlayLayers(overlay))
        self.layerBox.blockSignals(False)
        self._apply()

    def _apply(self) -> None:
        overlay = self.currentOverlay()
        layer = self.layerBox.currentText()
        hasOverlay = overlay is not None and bool(layer)
        self.layerBox.setVisible(hasOverlay)
        self.opacitySlider.setEnabled(hasOverlay)
        self.legend.setVisible(hasOverlay and layer == CLASSES)
        for viewport in self.viewports:
            if viewport.hasOverlayImage():
                viewport.removeOverlayImage()
        self.renderer = None
        if overlay is None or not layer:
            self._refreshViews()
            return
        raster, isRgb = overlayRaster(overlay, layer)
        renderer = ImageRenderer(image=raster)
        renderer.transparentNoData = True
        if isRgb:
            renderer.settings.mode.set(RenderMode.RGB)
            renderer.setManualStretch(0.0, 1.0)
        else:
            renderer.settings.mono.colorMap.set(pg.colormap.get(COLOR_MAP))
        renderer.settings.opacity.set(self.opacitySlider.value() / 100)
        self.renderer = renderer
        if layer == CLASSES:
            self.legend.setText(self._legendHtml(overlay))
        for viewport in self.viewports:
            viewport.overlayImage(renderer)
        self._refreshViews()

    def _refreshViews(self) -> None:
        for viewport in self.viewports:
            viewport.refresh()

    def _applyOpacity(self, value: int) -> None:
        if self.renderer is not None:
            self.renderer.settings.opacity.set(value / 100)
            self._refreshViews()

    @staticmethod
    def _legendHtml(raster: VardaRaster) -> str:
        names = raster.extraMetadata.get("classes", [])
        return "&nbsp;&nbsp;".join(
            f'<span style="color:{color}">&#9632;</span>&nbsp;{escape(str(name))}'
            for name, color in zip(names, classColors(raster))
        )
