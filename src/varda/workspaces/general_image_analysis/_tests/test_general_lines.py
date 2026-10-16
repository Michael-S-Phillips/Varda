"""Lines in the general workspace: drawn with Draw Line, listed, profiled,
marked on every view, and kept with the session."""

import numpy as np

from varda.image_rendering.raster_view.viewport_tools.line_tools import LineDrawTool
from varda.lines.line_collection import LineKind
from varda.utilities.debug import generate_random_image
from varda.workspaces.general_image_analysis import (
    GeneralImageAnalysisConfig,
    GeneralImageAnalysisWorkflow,
)
from varda.workspaces.workspace_kinds import buildWorkspace


def _workflow(qtbot, image):
    workflow = GeneralImageAnalysisWorkflow(GeneralImageAnalysisConfig([image]))
    qtbot.addWidget(workflow)
    return workflow


def test_a_drawn_line_is_listed_profiled_and_shown_on_every_view(qtbot):
    image = generate_random_image((30, 40, 10))
    workflow = _workflow(qtbot, image)
    workflow.toolManager2.activateTool(LineDrawTool)
    tool = workflow.toolManager2.activeTool
    tool.sigLineDrawn.emit(np.array([[2.0, 2.0], [30.0, 20.0]]), LineKind.STRAIGHT)
    (line,) = workflow.lineCollection.lines()
    assert workflow.lineManagerWidget.selectedFids() == [line.fid]
    assert list(workflow.profilePlot.profiles) == [line.fid]
    assert len(workflow.lineDisplay._handles[line.fid]) == 3  # all three views
    workflow.lineManagerWidget.deleteSelected()
    assert workflow.profilePlot.profiles == {} and workflow.lineDisplay._handles == {}


def test_the_kind_comes_from_the_lines_manager(qtbot):
    workflow = _workflow(qtbot, generate_random_image((20, 20, 10)))
    polyline = next(
        b
        for b in workflow.lineManagerWidget.kindButtons.buttons()
        if b.text() == "Polyline"
    )
    polyline.click()
    workflow.toolManager1.activateTool(LineDrawTool)
    assert workflow.toolManager1.activeTool._kind() == LineKind.POLYLINE


def test_lines_come_back_with_the_session(qtbot):
    image = generate_random_image((20, 20, 10))
    workflow = _workflow(qtbot, image)
    workflow.lineCollection.addLine([[1, 1], [10, 10]], name="Rim")
    state = workflow.sessionState()
    restored = buildWorkspace("general", [image], [image], state)
    qtbot.addWidget(restored)
    assert [line.name for line in restored.lineCollection.lines()] == ["Rim"]
