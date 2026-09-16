"""Pixel selection in the dual workspace plots the clicked viewport's image."""

import numpy as np
from PyQt6.QtCore import QPointF

from varda.image_rendering.raster_view.viewport_tools.pixel_select_tool import (
    PixelSelectTool,
)
from varda.utilities.debug import generate_random_image
from varda.workspaces.dual_image_workspace.dual_image_workspace import (
    DualImageWorkspace,
    DualImageWorkspaceConfig,
)


def test_secondary_viewport_selection_plots_secondary_image(qapp):
    primary = generate_random_image((20, 20, 10))
    secondary = generate_random_image((20, 20, 10))
    config = DualImageWorkspaceConfig([primary, secondary])
    config.image2Param.set(secondary)
    workspace = DualImageWorkspace(config)

    workspace.toolManager2.activateTool(PixelSelectTool)
    workspace.toolManager2.activeTool.sigPixelSelected.emit(QPointF(2.0, 3.0))

    assert workspace.pixelPlotDock.widget() is workspace.pixelPlotWidget
    (curve,) = workspace.pixelPlotWidget.pixelCurves
    _x, y = curve.plotDataItem.getData()
    np.testing.assert_array_equal(y, secondary.getSpectrum(2, 3).values)
