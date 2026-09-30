"""Pixel selection in the dual workspace: source selection and image labelling."""

import numpy as np
import pytest
from PyQt6.QtCore import QPointF

from varda.image_rendering.raster_view.viewport_tools.pixel_select_tool import (
    PixelSelectTool,
)
from varda.utilities.debug import generate_random_image
from varda.workspaces.dual_image_workspace.dual_image_workspace import (
    DualImageWorkspace,
    DualImageWorkspaceConfig,
    PixelSpectrumSource,
)


@pytest.fixture
def images():
    return generate_random_image((20, 20, 10)), generate_random_image((20, 20, 10))


@pytest.fixture
def workspace(qapp, images):
    primary, secondary = images
    config = DualImageWorkspaceConfig([primary, secondary])
    config.image2Param.set(secondary)
    return DualImageWorkspace(config)


def _select(workspace, toolManager, x: float, y: float) -> None:
    toolManager.activateTool(PixelSelectTool)
    toolManager.activeTool.sigPixelSelected.emit(QPointF(x, y))


def _curveValues(curve):
    _x, y = curve.plotDataItem.getData()
    return y


def test_primary_viewport_selection_plots_primary_image(workspace, images):
    primary, _secondary = images
    _select(workspace, workspace.toolManager1, 2.0, 3.0)

    assert workspace.pixelPlotDock.widget() is workspace.pixelPlotWidget
    (curve,) = workspace.pixelPlotWidget.pixelCurves
    np.testing.assert_array_equal(_curveValues(curve), primary.getSpectrum(2, 3).values)


def test_secondary_viewport_selection_plots_secondary_image(workspace, images):
    _primary, secondary = images
    _select(workspace, workspace.toolManager2, 2.0, 3.0)

    (curve,) = workspace.pixelPlotWidget.pixelCurves
    np.testing.assert_array_equal(
        _curveValues(curve), secondary.getSpectrum(2, 3).values
    )


def test_primary_source_plots_primary_even_when_secondary_is_clicked(workspace, images):
    primary, _secondary = images
    workspace.pixelSourceConfig.source.set(PixelSpectrumSource.PRIMARY)
    _select(workspace, workspace.toolManager2, 2.0, 3.0)

    (curve,) = workspace.pixelPlotWidget.pixelCurves
    np.testing.assert_array_equal(_curveValues(curve), primary.getSpectrum(2, 3).values)


def test_both_source_plots_both_images_labelled_by_name(workspace, images):
    primary, secondary = images
    workspace.pixelSourceConfig.source.set(PixelSpectrumSource.BOTH)
    _select(workspace, workspace.toolManager1, 2.0, 3.0)

    curves = workspace.pixelPlotWidget.pixelCurves
    assert [c.plotDataItem.name() for c in curves] == [
        f"{primary.name} (2, 3)",
        f"{secondary.name} (2, 3)",
    ]


def test_viewport_dock_titles_show_image_names(workspace, images):
    primary, secondary = images
    assert primary.name in workspace.viewport1Dock.windowTitle()
    assert secondary.name in workspace.viewport2Dock.windowTitle()
