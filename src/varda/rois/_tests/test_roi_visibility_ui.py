"""Hidden ROIs disappear from the image; the table and manager control them."""

from PyQt6.QtCore import Qt
from shapely.geometry import box

from varda.common.entities import Color, ROIMode
from varda.image_rendering.image_renderer import ImageRenderer
from varda.image_rendering.raster_view.image_viewport import ImageViewport
from varda.image_rendering.raster_view.overlay_handles import PyqtgraphROIOverlay
from varda.image_rendering.raster_view.roi_display_controller import (
    ROIDisplayController,
)
from varda.plotting.plot import VardaPlotWidget
from varda.rois.roi_collection import ROICollection
from varda.rois.roi_manager_widget import ROIManagerWidget
from varda.rois.roi_table_model import ROITableModel
from varda.rois.roi_table_view import ROITableView
from varda.utilities.debug import generate_random_image

RED = Color(1.0, 0.0, 0.0, 0.5)


def _collection() -> tuple[ROICollection, int, int]:
    collection = ROICollection()
    a = collection.addROI(box(1, 1, 4, 4), "a", RED, ROIMode.RECTANGLE)
    b = collection.addROI(box(5, 5, 8, 8), "b", RED, ROIMode.RECTANGLE)
    return collection, a, b


def _viewport(qtbot) -> ImageViewport:
    viewport = ImageViewport(ImageRenderer(image=generate_random_image((10, 10, 10))))
    qtbot.addWidget(viewport)
    return viewport


def _shown(controller: ROIDisplayController, viewportId: str, fid: int) -> bool:
    handle = controller._items[viewportId][fid]
    assert isinstance(handle, PyqtgraphROIOverlay)
    return handle.isVisible()


def test_a_hidden_roi_disappears_from_every_view(qtbot):
    collection, a, b = _collection()
    controller = ROIDisplayController(collection)
    controller.registerViewport("v1", _viewport(qtbot))
    collection.setVisible(a, False)
    assert not _shown(controller, "v1", a) and _shown(controller, "v1", b)
    controller.registerViewport("v2", _viewport(qtbot))  # opened later
    assert not _shown(controller, "v2", a)
    collection.setVisible(a, True)
    assert _shown(controller, "v1", a)


def test_the_table_has_a_show_checkbox_per_roi(qtbot):
    collection, a, _b = _collection()
    model = ROITableModel(collection)
    index = model.index(0, 0)
    assert model.flags(index) & Qt.ItemFlag.ItemIsUserCheckable
    assert model.data(index, Qt.ItemDataRole.CheckStateRole) == Qt.CheckState.Checked
    model.setData(index, Qt.CheckState.Unchecked.value, Qt.ItemDataRole.CheckStateRole)
    assert not collection.isVisible(a)
    assert (
        model.data(model.index(0, 0), Qt.ItemDataRole.CheckStateRole)
        == Qt.CheckState.Unchecked
    )


def test_the_manager_hides_and_shows_all(qtbot, make_split_image):
    collection, a, b = _collection()
    plot = VardaPlotWidget()
    qtbot.addWidget(plot)
    manager = ROIManagerWidget(collection, make_split_image(40, 20, 3, 8.0, 4.0), plot)
    qtbot.addWidget(manager)
    assert manager.visibilityButton.text() == "Hide All"
    manager.visibilityButton.click()
    assert not collection.isVisible(a) and not collection.isVisible(b)
    assert manager.visibilityButton.text() == "Show All"
    manager.visibilityButton.click()
    assert collection.isVisible(a) and collection.isVisible(b)


def test_a_row_can_be_shown_on_its_own(qtbot):
    collection, a, b = _collection()
    view = ROITableView(ROITableModel(collection))
    qtbot.addWidget(view)
    menu = view._buildRowMenu(b)
    (action,) = [x for x in menu.actions() if x.text() == "Show Only This ROI"]
    action.trigger()
    assert not collection.isVisible(a) and collection.isVisible(b)
