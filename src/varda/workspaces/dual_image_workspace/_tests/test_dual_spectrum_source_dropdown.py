"""Choosing a Spectrum Source in the sidebar dropdown must steer pixel plotting."""

import numpy as np
from PyQt6.QtCore import QPointF

from varda.common.parameter import EnumParameter
from varda.image_rendering.raster_view.viewport_tools.pixel_select_tool import (
    PixelSelectTool,
)
from varda.utilities.debug import generate_random_image
from varda.workspaces.dual_image_workspace.dual_image_workspace import (
    DualImageWorkspace,
    DualImageWorkspaceConfig,
    PixelSpectrumSource,
)


def test_dropdown_set_to_primary_plots_primary_from_a_secondary_click(qtbot):
    primary = generate_random_image((20, 20, 10))
    secondary = generate_random_image((20, 20, 10))
    config = DualImageWorkspaceConfig([primary, secondary])
    config.image2Param.set(secondary)
    workspace = DualImageWorkspace(config)
    qtbot.addWidget(workspace)

    dropdowns = [
        w
        for w in workspace.pixelPlotWidget.findChildren(
            EnumParameter.EnumParameterWidget
        )
        if w.param.name == "Spectrum Source"
    ]
    assert dropdowns, "Spectrum Source dropdown not found in the pixel plot sidebar"
    sources = list(PixelSpectrumSource)
    for dropdown in dropdowns:
        dropdown.comboBox.setCurrentIndex(sources.index(PixelSpectrumSource.PRIMARY))

    workspace.toolManager2.activateTool(PixelSelectTool)
    workspace.toolManager2.activeTool.sigPixelSelected.emit(QPointF(3.0, 5.0))

    (curve,) = workspace.pixelPlotWidget.pixelCurves
    _x, y = curve.plotDataItem.getData()
    np.testing.assert_array_equal(y, primary.getSpectrum(3, 5).values)
    assert curve.plotDataItem.name().startswith(primary.name)
