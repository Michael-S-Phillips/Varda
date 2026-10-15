"""Pixel selection in the general workspace plots into one persistent dock."""

from PyQt6.QtCore import QPointF

from varda.image_rendering.raster_view.viewport_tools.pixel_select_tool import (
    PixelSelectTool,
)
from varda.utilities.debug import generate_random_image
from varda.workspaces.general_image_analysis import (
    GeneralImageAnalysisConfig,
    GeneralImageAnalysisWorkflow,
)


def test_pixel_selections_accumulate_in_the_pixel_spectra_dock(qapp):
    image = generate_random_image((20, 20, 10))
    workflow = GeneralImageAnalysisWorkflow(GeneralImageAnalysisConfig([image]))

    workflow.toolManager1.activateTool(PixelSelectTool)
    tool = workflow.toolManager1.activeTool
    tool.sigPixelSelected.emit(QPointF(2.0, 3.0))
    tool.sigPixelSelected.emit(QPointF(4.0, 5.0))

    assert workflow.pixelPlotDock.widget() is workflow.pixelPlotWidget
    assert len(workflow.pixelPlotWidget.pixelCurves) == 2


def test_closing_the_pixel_dock_then_selecting_a_pixel_reopens_it(qapp):
    image = generate_random_image((20, 20, 10))
    workflow = GeneralImageAnalysisWorkflow(GeneralImageAnalysisConfig([image]))
    workflow.toolManager1.activateTool(PixelSelectTool)
    workflow.pixelPlotDock.toggleView(False)
    assert workflow.pixelPlotDock.isClosed()

    workflow.toolManager1.activeTool.sigPixelSelected.emit(QPointF(2.0, 3.0))

    assert not workflow.pixelPlotDock.isClosed()
    assert len(workflow.pixelPlotWidget.pixelCurves) == 1


def test_the_tool_uses_the_active_plots_window_and_outlines_it(qapp):
    image = generate_random_image((20, 20, 10))
    workflow = GeneralImageAnalysisWorkflow(GeneralImageAnalysisConfig([image]))
    workflow.toolManager1.activateTool(PixelSelectTool)
    tool = workflow.toolManager1.activeTool
    workflow.pixelPlotWidget.pixelConfig.windowWidth.set(3)
    workflow.pixelPlotWidget.pixelConfig.windowHeight.set(5)
    assert tool.windowProvider() == (3, 5)

    tool.isDragging = True
    tool._outlineWindow(10, 10)
    assert tool._windowOutline is not None
    tool._hideCrosshairs()
    assert tool._windowOutline is None

    tool.sigPixelSelected.emit(QPointF(10.0, 10.0))
    (curve,) = workflow.pixelPlotWidget.pixelCurves
    assert curve.plotDataItem.name() == "Region 3×5 at (10, 10)"
