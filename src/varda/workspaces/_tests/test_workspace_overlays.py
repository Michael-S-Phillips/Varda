"""Every image workspace can lay a classification (or any result) over its views."""

import numpy as np

from varda.common.entities import VardaRaster
from varda.common.di_types import ProjectImages
from varda.image_loading.data_sources.array_data_source import ArrayDataSource
from varda.utilities.debug import generate_random_image
from varda.workspaces.dual_image_workspace.dual_image_workspace import (
    DualImageWorkspace,
    DualImageWorkspaceConfig,
)
from varda.workspaces.general_image_analysis.general_image_analysis import (
    GeneralImageAnalysisConfig,
    GeneralImageAnalysisWorkflow,
)


def _classes(image: VardaRaster) -> VardaRaster:
    data = np.zeros((image.height, image.width, 1), dtype=np.float32)
    source = ArrayDataSource(
        data, bandNames=["Class"], extraMetadata={"classes": ["a"]}
    )
    return VardaRaster(source, name="classes")


def test_the_general_workspace_overlays_on_all_three_views(qtbot):
    image = generate_random_image((20, 30, 10))
    images = ProjectImages([image])
    workspace = GeneralImageAnalysisWorkflow(GeneralImageAnalysisConfig(images))
    qtbot.addWidget(workspace)
    result = _classes(image)
    images.append(result)  # a classification finishes while the workspace is open
    workspace.overlayBar.setOverlay(result)
    view = workspace.tripleRasterView
    assert all(
        v.hasOverlayImage() for v in (view.viewport1, view.viewport2, view.viewport3)
    )


def test_the_dual_workspace_overlays_each_side(qtbot):
    first = generate_random_image((20, 30, 10))
    second = generate_random_image((20, 30, 10))
    result = _classes(second)
    config = DualImageWorkspaceConfig([first, second, result])
    config.image1Param.set(first)
    config.image2Param.set(second)
    workspace = DualImageWorkspace(config)
    qtbot.addWidget(workspace)
    workspace.overlayBar2.setOverlay(result)
    assert workspace.viewport2.hasOverlayImage()
    assert not workspace.viewport1.hasOverlayImage()
