"""Tests for pre-filling the New Dual Image Workspace dialog."""

from varda.utilities.debug import generate_random_image
from varda.workspaces.dual_image_workspace import NewDualImageWorkspaceDialog


def test_dialog_prefills_primary_and_secondary(qapp):
    first = generate_random_image((20, 20, 10))
    second = generate_random_image((20, 20, 10))
    third = generate_random_image((20, 20, 10))

    dialog = NewDualImageWorkspaceDialog(
        [first, second, third], primary=second, secondary=third
    )

    config = dialog.dualImageWorkspaceConfig
    assert config.image1Param.get() is second
    assert config.image2Param.get() is third


def test_dialog_prefilling_only_primary_leaves_secondary_at_default(qapp):
    first = generate_random_image((20, 20, 10))
    second = generate_random_image((20, 20, 10))

    dialog = NewDualImageWorkspaceDialog([first, second], primary=second)

    config = dialog.dualImageWorkspaceConfig
    assert config.image1Param.get() is second
    assert config.image2Param.get() is first
