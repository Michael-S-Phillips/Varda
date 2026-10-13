"""The Draw ROI tool stays armed: shape after shape, in the chosen shape type."""

import pytest
from PyQt6.QtCore import QEvent, QPointF, Qt

from varda.common.entities import ROIMode
from varda.image_rendering.image_renderer import ImageRenderer
from varda.image_rendering.raster_view.image_viewport import ImageViewport
from varda.image_rendering.raster_view.pointer_event import (
    KeyEvent,
    PointerAction,
    PointerEvent,
)
from varda.image_rendering.raster_view.viewport_tools.roi_tools import ROIDrawTool
from varda.utilities.debug import generate_random_image

LEFT, RIGHT = Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton
NONE = Qt.MouseButton.NoButton


@pytest.fixture
def tool(qtbot):
    viewport = ImageViewport(ImageRenderer(image=generate_random_image((50, 50, 10))))
    qtbot.addWidget(viewport)
    tool = ROIDrawTool(viewport)
    tool.activate()
    shapes = []
    tool.sigROIDrawingComplete.connect(shapes.append)
    yield tool, shapes
    tool.deactivate()


def _event(action, x, y, button=LEFT):
    pos = QPointF(x, y)
    return PointerEvent(action, pos, pos, button, Qt.KeyboardModifier.NoModifier)


def _drag(tool, points, button=LEFT):
    (x0, y0), *rest = points
    results = [tool.onPointerEvent(_event(PointerAction.PRESS, x0, y0, button))]
    for x, y in rest:
        results.append(tool.onPointerEvent(_event(PointerAction.MOVE, x, y, NONE)))
    x, y = points[-1]
    results.append(tool.onPointerEvent(_event(PointerAction.RELEASE, x, y, button)))
    return results


def _key(tool, key):
    return tool.onKeyEvent(KeyEvent(key, Qt.KeyboardModifier.NoModifier))


def test_freehand_shapes_can_be_drawn_one_after_another(tool):
    tool, shapes = tool
    _drag(tool, [(10, 10), (20, 10), (20, 20), (10, 20)])
    _drag(tool, [(30, 30), (40, 30), (40, 40)])
    assert len(shapes) == 2
    assert all(s["roiType"] == ROIMode.FREEHAND for s in shapes)
    assert shapes[0]["geometry"].area > 0


def test_rectangles_and_ellipses_follow_the_drag(tool):
    tool, shapes = tool
    tool.setShape(ROIMode.RECTANGLE)
    _drag(tool, [(10, 10), (15, 12), (30, 20)])
    assert shapes[-1]["roiType"] == ROIMode.RECTANGLE
    assert shapes[-1]["geometry"].bounds == pytest.approx((10, 10, 30, 20))
    tool.setShape(ROIMode.ELLIPSE)
    _drag(tool, [(10, 10), (30, 30)])
    assert shapes[-1]["roiType"] == ROIMode.ELLIPSE
    assert len(shapes) == 2


def test_a_click_without_a_drag_draws_nothing_and_stays_armed(tool):
    tool, shapes = tool
    tool.setShape(ROIMode.RECTANGLE)
    _drag(tool, [(10, 10), (11, 11)])
    assert shapes == []
    _drag(tool, [(10, 10), (30, 30)])
    assert len(shapes) == 1


def test_polygons_add_a_vertex_per_click_and_finish_with_enter(tool):
    tool, shapes = tool
    tool.setShape(ROIMode.POLYGON)
    for x, y in [(10, 10), (30, 10), (30, 30), (10, 30)]:
        tool.onPointerEvent(_event(PointerAction.PRESS, x, y))
        tool.onPointerEvent(_event(PointerAction.RELEASE, x, y))
    assert _key(tool, Qt.Key.Key_Backspace)  # drop (10, 30)
    assert _key(tool, Qt.Key.Key_Return)
    assert len(shapes) == 1
    assert len(shapes[0]["geometry"].exterior.coords) == 4  # 3 vertices + closing


def _clickCorners(tool, corners):
    for x, y in corners:
        tool.onPointerEvent(_event(PointerAction.PRESS, x, y))
        tool.onPointerEvent(_event(PointerAction.RELEASE, x, y))


def test_double_clicking_finishes_a_polygon(tool):
    """Qt sends a double-click's second click as its own event."""
    tool, shapes = tool
    tool.setShape(ROIMode.POLYGON)
    _clickCorners(tool, [(10, 10), (30, 10), (30, 30)])
    assert tool.onPointerEvent(_event(PointerAction.DOUBLE_CLICK, 30, 30))
    tool.onPointerEvent(_event(PointerAction.RELEASE, 30, 30))
    assert len(shapes) == 1
    assert len(shapes[0]["geometry"].exterior.coords) == 4


def test_right_clicking_finishes_a_polygon(tool):
    tool, shapes = tool
    tool.setShape(ROIMode.POLYGON)
    _clickCorners(tool, [(10, 10), (30, 10), (30, 30)])
    assert tool.onPointerEvent(_event(PointerAction.PRESS, 30, 30, RIGHT))
    assert len(shapes) == 1


def test_right_clicking_a_polygon_with_too_few_corners_drops_it(tool):
    tool, shapes = tool
    tool.setShape(ROIMode.POLYGON)
    _clickCorners(tool, [(10, 10), (30, 10)])
    assert tool.onPointerEvent(_event(PointerAction.PRESS, 30, 30, RIGHT))
    assert shapes == [] and not tool.isSketching()


def test_escape_and_right_click_cancel_a_shape_in_progress_only(tool):
    tool, shapes = tool
    tool.onPointerEvent(_event(PointerAction.PRESS, 10, 10))
    tool.onPointerEvent(_event(PointerAction.MOVE, 20, 20, NONE))
    assert _key(tool, Qt.Key.Key_Escape)
    assert not _key(tool, Qt.Key.Key_Escape)  # nothing to cancel: let it through
    tool.onPointerEvent(_event(PointerAction.PRESS, 10, 10))
    assert tool.onPointerEvent(_event(PointerAction.PRESS, 12, 12, RIGHT))
    assert not tool.onPointerEvent(_event(PointerAction.PRESS, 12, 12, RIGHT))  # menu
    assert shapes == []


def test_hovering_while_idle_is_left_to_the_view(tool):
    tool, _ = tool
    assert not tool.onPointerEvent(_event(PointerAction.MOVE, 10, 10, NONE))


def test_changing_the_shape_mid_drawing_drops_the_unfinished_shape(tool):
    tool, shapes = tool
    tool.setShape(ROIMode.POLYGON)
    tool.onPointerEvent(_event(PointerAction.PRESS, 10, 10))
    tool.setShape(ROIMode.RECTANGLE)
    assert not tool.isSketching()
    _drag(tool, [(10, 10), (30, 30)])
    assert [s["roiType"] for s in shapes] == [ROIMode.RECTANGLE]


CMD = Qt.KeyboardModifier.ControlModifier  # Qt's name for Cmd on macOS


def test_cmd_drag_is_left_to_the_view_for_panning(tool):
    tool, shapes = tool
    for action, button in [
        (PointerAction.PRESS, LEFT),
        (PointerAction.MOVE, NONE),
        (PointerAction.RELEASE, LEFT),
    ]:
        pos = QPointF(10, 10)
        assert not tool.onPointerEvent(PointerEvent(action, pos, pos, button, CMD))
    assert shapes == [] and not tool.isSketching()


def test_panning_mid_polygon_keeps_the_polygon(tool):
    tool, shapes = tool
    tool.setShape(ROIMode.POLYGON)
    for x, y in [(10, 10), (30, 10)]:
        tool.onPointerEvent(_event(PointerAction.PRESS, x, y))
    pos = QPointF(40, 40)
    tool.onPointerEvent(PointerEvent(PointerAction.PRESS, pos, pos, LEFT, CMD))
    tool.onPointerEvent(PointerEvent(PointerAction.RELEASE, pos, pos, LEFT, CMD))
    tool.onPointerEvent(_event(PointerAction.PRESS, 30, 30))
    _key(tool, Qt.Key.Key_Return)
    assert len(shapes[0]["geometry"].exterior.coords) == 4  # the pan added no vertex


class _FakeDoubleClick:
    """What the view reads from a scene double-click (PyQt can't build one)."""

    def type(self):
        return QEvent.Type.GraphicsSceneMouseDoubleClick

    def scenePos(self):
        return QPointF(10, 10)

    def button(self):
        return LEFT

    def modifiers(self):
        return Qt.KeyboardModifier.NoModifier

    def accept(self):
        pass


def test_the_view_hands_double_clicks_to_the_tool(qtbot):
    viewport = ImageViewport(ImageRenderer(image=generate_random_image((50, 50, 10))))
    qtbot.addWidget(viewport)
    seen = []

    class _Recorder:
        def onPointerEvent(self, event):
            seen.append(event.action)
            return True

    viewport.installTool(_Recorder())
    viewport.eventFilter(viewport._imageItem, _FakeDoubleClick())
    assert seen == [PointerAction.DOUBLE_CLICK]
