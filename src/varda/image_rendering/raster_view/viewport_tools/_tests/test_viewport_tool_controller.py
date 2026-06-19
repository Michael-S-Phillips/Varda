from __future__ import annotations

from collections.abc import Sequence
from typing import cast

from varda.image_rendering.raster_view.image_viewport import ImageViewport
from varda.image_rendering.raster_view.viewport_tools.viewport_tool import (
    ViewportTool,
)
from varda.image_rendering.raster_view.viewport_tools.viewport_tool_controller import (
    ViewportToolController,
)
from varda.image_rendering.raster_view.viewport_tools.pixel_select_tool import (
    PixelSelectTool,
)
from varda.image_rendering.raster_view.viewport_tools.roi_tools import (
    FreehandROITool,
    RectangleROITool,
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

    def modalTools(self) -> list[ViewportTool]:
        return [t for t in self.installedTools if not t.isAmbient]

    def ambientTools(self) -> list[ViewportTool]:
        return [t for t in self.installedTools if t.isAmbient]


def _controller(nViewports=2):
    viewports = [_FakeViewport() for _ in range(nViewports)]
    controller = ViewportToolController(cast(Sequence[ImageViewport], viewports))
    return controller, viewports


def test_ambient_tools_installed_on_every_viewport_at_construction(qtbot):
    _, viewports = _controller()
    for vp in viewports:
        ambient = vp.ambientTools()
        assert len(ambient) == 1
        assert isinstance(ambient[0], PixelSelectTool)


def test_toolbar_excludes_ambient_tools(qtbot):
    controller, _ = _controller()
    labels = [action.text() for action in controller.toolBar.actions()]
    assert PixelSelectTool.toolName not in labels
    assert FreehandROITool.toolName in labels


def test_activate_modal_arms_every_viewport(qtbot):
    controller, viewports = _controller()
    controller.activateTool(FreehandROITool)
    assert len(controller._modalInstances) == len(viewports)
    for vp in viewports:
        modal = vp.modalTools()
        assert len(modal) == 1
        assert isinstance(modal[0], FreehandROITool)
        # ambient tool is still present alongside the modal one
        assert len(vp.ambientTools()) == 1


def test_completion_disarms_all_viewports(qtbot):
    controller, viewports = _controller()
    controller.activateTool(FreehandROITool)
    oneInstance = next(iter(controller._modalInstances.values()))

    oneInstance.sigCompleted.emit()

    assert controller._modalInstances == {}
    for vp in viewports:
        assert vp.modalTools() == []
        assert len(vp.ambientTools()) == 1  # ambient survives


def test_switching_modal_replaces_previous(qtbot):
    controller, viewports = _controller()
    controller.activateTool(FreehandROITool)
    controller.activateTool(RectangleROITool)
    for vp in viewports:
        modal = vp.modalTools()
        assert len(modal) == 1
        assert isinstance(modal[0], RectangleROITool)
