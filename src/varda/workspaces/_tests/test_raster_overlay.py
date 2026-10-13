"""Overlaying a co-registered project image (e.g. a classification) on a workspace view."""

import numpy as np
import pytest
from affine import Affine

from varda.common.di_types import ProjectImages
from varda.common.entities import VardaRaster
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.image_rendering.image_renderer import ImageRenderer
from varda.image_rendering.raster_view.image_viewport import ImageViewport
from varda.workspaces.raster_overlay import (
    CLASSES,
    NO_OVERLAY,
    OverlayBar,
    compatibleImages,
    overlayLayers,
    overlayRaster,
)


def _raster(data, name, **kwargs) -> VardaRaster:
    data = np.asarray(data, dtype=np.float32)
    if data.ndim == 2:
        data = data[:, :, None]
    return VardaRaster(ArrayDataSource(data, **kwargs), name=name)


def _base() -> VardaRaster:
    rng = np.random.default_rng(0)
    return _raster(rng.random((6, 8, 4)), "scene")


def _classification(base: VardaRaster, colors=True) -> VardaRaster:
    classes = np.zeros((6, 8))
    classes[:, 4:] = 1
    classes[0, 0] = np.nan
    probs = np.stack([1 - classes, classes], axis=2)
    data = np.concatenate([classes[:, :, None], probs], axis=2)
    metadata = {"classes": ["dark", "bright"]}
    if colors:
        metadata["classColors"] = ["#ff0000", "#0000ff"]
    return _raster(
        data,
        "scene MLP classes",
        bandNames=["Class", "P(dark)", "P(bright)"],
        extraMetadata=metadata,
    )


def test_only_images_on_the_same_grid_are_offered():
    base = _base()
    same = _classification(base)
    smaller = _raster(np.zeros((3, 8)), "smaller")
    elsewhere = _raster(
        np.zeros((6, 8)),
        "elsewhere",
        transform=Affine.translation(100, 0),
        crs="EPSG:4326",
    )
    assert compatibleImages([base, same, smaller, elsewhere], base) == [same]


def test_a_classification_offers_its_classes_then_each_probability():
    assert overlayLayers(_classification(_base())) == [CLASSES, "P(dark)", "P(bright)"]
    assert overlayLayers(_raster(np.zeros((6, 8, 2)), "x", bandNames=["a", "b"])) == [
        "a",
        "b",
    ]


def test_the_classes_layer_paints_each_class_its_colour_and_leaves_gaps_empty():
    raster, isRgb = overlayRaster(_classification(_base()), CLASSES)
    assert isRgb
    rgb = raster.getData()
    np.testing.assert_allclose(rgb[1, 1], [1, 0, 0])
    np.testing.assert_allclose(rgb[1, 6], [0, 0, 1])
    assert np.isnan(rgb[0, 0]).all()


def test_classes_without_stored_colours_get_distinct_ones():
    raster, _ = overlayRaster(_classification(_base(), colors=False), CLASSES)
    rgb = raster.getData()
    assert not np.allclose(rgb[1, 1], rgb[1, 6])


def test_a_band_layer_is_a_single_band_image():
    raster, isRgb = overlayRaster(_classification(_base()), "P(bright)")
    assert not isRgb and raster.bandCount == 1
    np.testing.assert_allclose(raster.getData()[1, 6, 0], 1.0)


def test_no_data_is_transparent_when_asked():
    renderer = ImageRenderer(image=overlayRaster(_classification(_base()), CLASSES)[0])
    renderer.transparentNoData = True
    rgba = renderer.render()
    assert rgba[0, 0, 3] == 0 and rgba[1, 1, 3] > 0


@pytest.fixture
def bar(qtbot):
    base = _base()
    images = [base, _classification(base)]
    viewports = [ImageViewport(ImageRenderer(image=base)) for _ in range(2)]
    for viewport in viewports:
        qtbot.addWidget(viewport)
    widget = OverlayBar(images, base, viewports)
    qtbot.addWidget(widget)
    return widget, viewports, images


def test_choosing_an_image_overlays_it_on_every_view(bar):
    widget, viewports, images = bar
    assert widget.imageBox.itemText(0) == NO_OVERLAY
    assert widget.imageBox.count() == 2  # the base image itself is not offered
    widget.setOverlay(images[1])
    assert widget.layerBox.currentText() == CLASSES
    assert all(v.hasOverlayImage() for v in viewports)
    assert widget.legend.isVisibleTo(widget)
    assert "dark" in widget.legend.text() and "bright" in widget.legend.text()
    widget.setOverlay(None)
    assert not any(v.hasOverlayImage() for v in viewports)


def test_opacity_and_layer_changes_apply(bar):
    widget, viewports, images = bar
    widget.setOverlay(images[1])
    widget.opacitySlider.setValue(30)
    assert widget.renderer is not None
    assert widget.renderer.settings.opacity.get() == pytest.approx(0.3)
    widget.layerBox.setCurrentText("P(dark)")
    assert not widget.legend.isVisibleTo(widget)
    assert widget.renderer.settings.opacity.get() == pytest.approx(0.3)


def test_new_results_appear_in_the_list(qtbot):
    base = _base()
    images = ProjectImages([base])
    widget = OverlayBar(images, base, [])
    qtbot.addWidget(widget)
    assert widget.imageBox.count() == 1
    images.append(_classification(base))
    assert widget.imageBox.count() == 2


def test_the_overlay_sits_between_the_image_and_what_is_drawn_on_it(bar):
    widget, viewports, images = bar
    widget.setOverlay(images[1])
    viewport = viewports[0]
    outline = viewport.addPolygonOverlay()
    assert viewport._imageItem.zValue() < viewport._overlayImageItem.zValue()
    assert viewport._overlayImageItem.zValue() < outline._item.zValue()
