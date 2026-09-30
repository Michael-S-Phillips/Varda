"""Tests for pre-filling the New Dual Image Workspace dialog."""

from varda.common.parameter import ImageParameter
from varda.utilities.debug import generate_random_image
from varda.workspaces.dual_image_workspace import NewDualImageWorkspaceDialog


def _images(n):
    return [generate_random_image((20, 20, 10)) for _ in range(n)]


def test_dialog_prefills_primary_and_secondary(qapp):
    first, second, third = _images(3)

    dialog = NewDualImageWorkspaceDialog(
        [first, second, third], primary=second, secondary=third
    )

    config = dialog.dualImageWorkspaceConfig
    assert config.image1Param.get() is second
    assert config.image2Param.get() is third


def test_dialog_prefilling_only_primary_leaves_secondary_at_default(qapp):
    first, second = _images(2)

    dialog = NewDualImageWorkspaceDialog([first, second], primary=second)

    config = dialog.dualImageWorkspaceConfig
    assert config.image1Param.get() is second
    assert config.image2Param.get() is first


def test_dialog_dropdowns_display_the_prefilled_images(qapp):
    first, second, third = _images(3)
    dialog = NewDualImageWorkspaceDialog(
        [first, second, third], primary=second, secondary=third
    )

    dropdowns = dialog.findChildren(ImageParameter.ImageParameterWidget)
    shown = {w.param.name: w.comboBox.currentIndex() for w in dropdowns}
    assert shown == {"Primary Image": 1, "Secondary Image": 2}


def test_accepting_a_prefilled_dialog_opens_the_workspace_on_those_images(qtbot):
    first, second, third = _images(3)
    dialog = NewDualImageWorkspaceDialog(
        [first, second, third], primary=second, secondary=third
    )
    qtbot.addWidget(dialog)
    created = []
    dialog.connectOnAccept(created.append)

    dialog.accept()

    (workspace,) = created
    # qtbot closes the workspace and drains its posted events before deletion;
    # letting it be garbage-collected instead leaves dangling scene events.
    qtbot.addWidget(workspace)
    assert workspace.image1 is second
    assert workspace.image2 is third
