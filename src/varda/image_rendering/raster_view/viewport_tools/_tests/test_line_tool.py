"""Draw Line: straight lines (drag, or two clicks), polylines and freehand."""

import numpy as np
import pytest
from PyQt6.QtCore import QPointF, Qt

from varda.image_rendering.image_renderer import ImageRenderer
from varda.image_rendering.raster_view.image_viewport import ImageViewport
from varda.image_rendering.raster_view.pointer_event import (
    KeyEvent,
    PointerAction,
    PointerEvent,
)
from varda.image_rendering.raster_view.viewport_tools.line_tools import LineDrawTool
from varda.lines.line_collection import LineKind
from varda.utilities.debug import generate_random_image

LEFT, RIGHT = Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton
NONE = Qt.KeyboardModifier.NoModifier


def _event(action, x, y, button=LEFT, modifiers=NONE):
    pos = QPointF(x, y)
    return PointerEvent(action, pos, pos, button, modifiers)


@pytest.fixture
def tool(qtbot):
    viewport = ImageViewport(ImageRenderer(image=generate_random_image((40, 60, 10))))
    qtbot.addWidget(viewport)
    tool = LineDrawTool(viewport)
    tool.activate()
    yield tool
    tool.deactivate()


@pytest.fixture
def drawn(tool):
    lines = []
    tool.sigLineDrawn.connect(lambda vertices, kind: lines.append((vertices, kind)))
    return lines


def _use(tool, kind):
    tool.setKindProvider(lambda: kind)


def test_a_straight_line_is_dragged_from_end_to_end(tool, drawn):
    _use(tool, LineKind.STRAIGHT)
    tool.onPointerEvent(_event(PointerAction.PRESS, 5, 5))
    tool.onPointerEvent(_event(PointerAction.MOVE, 20, 10))
    tool.onPointerEvent(_event(PointerAction.RELEASE, 30, 12))
    ((vertices, kind),) = drawn
    assert kind == LineKind.STRAIGHT
    np.testing.assert_allclose(vertices, [[5, 5], [30, 12]])


def test_a_straight_line_can_be_two_clicks(tool, drawn):
    _use(tool, LineKind.STRAIGHT)
    tool.onPointerEvent(_event(PointerAction.PRESS, 5, 5))
    tool.onPointerEvent(_event(PointerAction.RELEASE, 5, 5))
    assert drawn == [] and tool.isDrawing()
    tool.onPointerEvent(_event(PointerAction.MOVE, 15, 9))
    tool.onPointerEvent(_event(PointerAction.PRESS, 25, 9))
    np.testing.assert_allclose(drawn[0][0], [[5, 5], [25, 9]])


def test_a_polyline_takes_clicks_backspace_and_finishes_on_double_click(tool, drawn):
    _use(tool, LineKind.POLYLINE)
    for x, y in ((2, 2), (10, 2), (10, 30), (40, 30)):
        tool.onPointerEvent(_event(PointerAction.PRESS, x, y))
        tool.onPointerEvent(_event(PointerAction.RELEASE, x, y))
    tool.onKeyEvent(KeyEvent(Qt.Key.Key_Backspace, NONE))  # drops (40, 30)
    tool.onPointerEvent(_event(PointerAction.PRESS, 20, 35))
    tool.onPointerEvent(_event(PointerAction.DOUBLE_CLICK, 20, 35))
    ((vertices, kind),) = drawn
    assert kind == LineKind.POLYLINE
    np.testing.assert_allclose(vertices, [[2, 2], [10, 2], [10, 30], [20, 35]])


def test_a_freehand_stroke_is_thinned(tool, drawn):
    _use(tool, LineKind.FREEHAND)
    tool.onPointerEvent(_event(PointerAction.PRESS, 0, 10))
    for x in np.linspace(0.5, 50, 100):
        tool.onPointerEvent(_event(PointerAction.MOVE, x, 10 + 0.05 * np.sin(x)))
    tool.onPointerEvent(_event(PointerAction.RELEASE, 50, 10))
    ((vertices, kind),) = drawn
    assert kind == LineKind.FREEHAND and 2 <= len(vertices) < 10


def test_escape_drops_the_line_in_progress(tool, drawn):
    _use(tool, LineKind.POLYLINE)
    tool.onPointerEvent(_event(PointerAction.PRESS, 2, 2))
    tool.onKeyEvent(KeyEvent(Qt.Key.Key_Escape, NONE))
    assert not tool.isDrawing() and drawn == []


def test_cmd_drag_still_pans(tool, drawn):
    _use(tool, LineKind.STRAIGHT)
    used = tool.onPointerEvent(
        _event(PointerAction.PRESS, 5, 5, modifiers=Qt.KeyboardModifier.ControlModifier)
    )
    assert used is False and not tool.isDrawing()
