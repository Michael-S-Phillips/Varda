"""The shape picker, the class picker, and the controller that ties the
Draw ROI tool under each view to them."""

import pytest
from PyQt6.QtCore import QPointF, Qt
from shapely.geometry import box

from varda.common.entities import Color, ROIMode
from varda.image_rendering.image_renderer import ImageRenderer
from varda.image_rendering.raster_view.image_viewport import ImageViewport
from varda.image_rendering.raster_view.pointer_event import PointerAction, PointerEvent
from varda.image_rendering.raster_view.viewport_tools.roi_tools import ROIDrawTool
from varda.image_rendering.raster_view.viewport_tools.tool_manager import ToolManager
from varda.rois.roi_collection import ROICollection
from varda.rois.roi_drawing_state import ROIDrawingState
from varda.rois.roi_drawing_widgets import (
    ROIClassPicker,
    ROIDrawingController,
    ROIShapePicker,
)
from varda.utilities.debug import generate_random_image


@pytest.fixture
def state():
    return ROIDrawingState(ROICollection())


def test_the_shape_picker_sets_and_follows_the_shape(qtbot, state):
    picker = ROIShapePicker(state)
    qtbot.addWidget(picker)
    assert picker.buttons[ROIMode.FREEHAND].isChecked()
    picker.buttons[ROIMode.POLYGON].click()
    assert state.shape == ROIMode.POLYGON
    state.setShape(ROIMode.ELLIPSE)
    assert picker.buttons[ROIMode.ELLIPSE].isChecked()
    assert not picker.buttons[ROIMode.POLYGON].isChecked()


def test_the_class_picker_lists_classes_and_starts_new_ones(qtbot, state):
    picker = ROIClassPicker(state)
    qtbot.addWidget(picker)
    assert picker.classBox.count() == 0
    state.collection.addROI(box(0, 0, 2, 2), "basalt", Color.black(), ROIMode.POLYGON)
    state.collection.addROI(box(3, 3, 5, 5), "basalt", Color.black(), ROIMode.POLYGON)
    assert picker.classBox.itemText(0) == "basalt (2)"
    picker.newButton.click()
    assert state.activeClass == "Class 1"
    assert picker.classBox.currentText() == "Class 1 (new)"
    picker.classBox.setCurrentIndex(0)
    assert state.activeClass == "basalt"


def test_two_pickers_stay_in_step(qtbot, state):
    first, second = ROIClassPicker(state), ROIClassPicker(state)
    qtbot.addWidget(first)
    qtbot.addWidget(second)
    first.newButton.click()
    assert second.classBox.currentText() == "Class 1 (new)"


def _press(tool, x, y, action=PointerAction.PRESS):
    pos = QPointF(x, y)
    tool.onPointerEvent(
        PointerEvent(
            action, pos, pos, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier
        )
    )


@pytest.fixture
def wired(qtbot, state):
    viewports = [
        ImageViewport(ImageRenderer(image=generate_random_image((50, 50, 10))))
        for _ in range(2)
    ]
    for viewport in viewports:
        qtbot.addWidget(viewport)
    managers = [ToolManager(v) for v in viewports]
    controller = ROIDrawingController(state, managers)
    yield managers, controller
    for manager in managers:
        manager.deactivateCurrentTool()


def test_drawing_adds_shapes_to_the_active_class_in_the_chosen_shape(wired, state):
    managers, controller = wired
    state.setShape(ROIMode.RECTANGLE)
    managers[0].activateTool(ROIDrawTool)
    tool = managers[0].activeTool
    assert tool.shape == ROIMode.RECTANGLE
    for x, y in [(10, 10), (30, 30)]:
        _press(tool, x, y, PointerAction.PRESS if x == 10 else PointerAction.MOVE)
    _press(tool, 30, 30, PointerAction.RELEASE)
    assert state.collection.classes() == {"Class 1": [0]}
    state.setShape(ROIMode.ELLIPSE)  # picked in the ROI manager while drawing
    assert tool.shape == ROIMode.ELLIPSE


def test_the_class_picker_shows_under_a_view_only_while_drawing_there(wired):
    managers, controller = wired
    assert not controller.classBarVisible(managers[0])
    managers[0].activateTool(ROIDrawTool)
    assert controller.classBarVisible(managers[0])
    assert not controller.classBarVisible(managers[1])
    managers[0].deactivateCurrentTool()
    assert not controller.classBarVisible(managers[0])
