from __future__ import annotations

from typing import cast

from PyQt6.QtCore import QPointF

from varda.image_rendering.raster_view.image_viewport import ImageViewport
from varda.image_rendering.raster_view.viewport_tools.viewport_tool import (
    ViewportTool,
)
from varda.image_rendering.raster_view.viewport_tools.pixel_select_tool import (
    PixelSelectTool,
)
from varda.image_rendering.raster_view.viewport_tools.roi_tools import (
    RectangleROITool,
    FreehandROITool,
)
from varda.image_rendering.raster_view.viewport_tools.tool_registry import (
    ToolRegistry,
)


class _FakeImage:
    hasGeospatialData = False


class _FakeHandle:
    def setPoints(self, points):
        pass

    def setText(self, text):
        pass

    def remove(self):
        pass


class _FakeViewport:
    """Minimal stand-in for ImageViewport used by tool unit tests."""

    def __init__(self):
        self.installedTools: list[ViewportTool] = []
        self.imageEntity = _FakeImage()

    def installTool(self, tool):
        if tool not in self.installedTools:
            self.installedTools.append(tool)

    def removeTool(self, tool):
        if tool in self.installedTools:
            self.installedTools.remove(tool)

    def installEventFilter(self, obj):
        pass

    def addCrosshair(self, color=None):
        return _FakeHandle()

    def addPolygonOverlay(self, *args, **kwargs):
        return _FakeHandle()

    def addTextOverlay(self, *args, **kwargs):
        return _FakeHandle()

    def localToImage(self, points):
        return [(float(x), float(y)) for x, y in points]


def test_pixel_select_is_ambient():
    assert PixelSelectTool.isAmbient is True


def test_roi_tools_are_not_ambient():
    assert FreehandROITool.isAmbient is False


def test_default_tool_is_not_ambient():
    assert ViewportTool.isAmbient is False


def test_registry_lists_pixel_select_as_ambient():
    registry = ToolRegistry()
    assert PixelSelectTool in registry.getAmbientTools()
    assert FreehandROITool not in registry.getAmbientTools()


def test_completed_signal_fires_on_roi_completion(qtbot):
    viewport = _FakeViewport()
    tool = RectangleROITool(cast(ImageViewport, viewport))
    tool.activate()
    tool.points = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    tool.startPoint = QPointF(0.0, 0.0)

    with qtbot.waitSignal(tool.sigCompleted, timeout=1000):
        tool.completeDrawing()
