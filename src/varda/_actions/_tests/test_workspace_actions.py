"""The Workspace menu offers closing the current workspace."""

from app_model.types import StandardKeyBinding

from varda._actions._menu_ids import MenuId
from varda._actions._workspace_actions import WORKSPACE_ACTIONS


def test_close_workspace_action_is_in_the_workspace_menu_with_cmd_w():
    (action,) = [a for a in WORKSPACE_ACTIONS if a.id == "varda.workspace.close"]
    assert action.title == "Close Workspace"
    assert any(rule.id == MenuId.WORKSPACE for rule in action.menus)
    assert action.keybindings == [StandardKeyBinding.Close.to_keybinding_rule()]
    assert action.enablement is not None  # only when a workspace is open
