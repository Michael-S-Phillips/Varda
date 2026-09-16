"""Toolbar tool buttons toggle: click the active tool again to go back to navigating."""

import pytest

from varda.image_rendering.image_renderer import ImageRenderer
from varda.image_rendering.raster_view.image_viewport import ImageViewport
from varda.image_rendering.raster_view.viewport_tools.pixel_select_tool import (
    PixelSelectTool,
)
from varda.image_rendering.raster_view.viewport_tools.ratio_explorer_tool import (
    RatioExplorerTool,
)
from varda.image_rendering.raster_view.viewport_tools.tool_manager import ToolManager
from varda.utilities.debug import generate_random_image


@pytest.fixture
def manager(qtbot):
    viewport = ImageViewport(ImageRenderer(image=generate_random_image((20, 20, 10))))
    qtbot.addWidget(viewport)
    manager = ToolManager(viewport)
    yield manager
    manager.deactivateCurrentTool()
    del viewport


def _actionFor(manager: ToolManager, toolClass):
    (action,) = [a for a in manager.getToolbar().actions() if a.data() is toolClass]
    return action


def test_clicking_the_active_tool_again_deactivates_it(manager):
    action = _actionFor(manager, RatioExplorerTool)

    action.trigger()
    assert isinstance(manager.activeTool, RatioExplorerTool)
    assert action.isChecked()

    action.trigger()
    assert manager.activeTool is None
    assert not action.isChecked()


def test_clicking_another_tool_switches_to_it(manager):
    _actionFor(manager, RatioExplorerTool).trigger()
    _actionFor(manager, PixelSelectTool).trigger()

    assert isinstance(manager.activeTool, PixelSelectTool)
    assert not _actionFor(manager, RatioExplorerTool).isChecked()
