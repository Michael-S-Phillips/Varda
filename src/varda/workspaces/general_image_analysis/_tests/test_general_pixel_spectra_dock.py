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
