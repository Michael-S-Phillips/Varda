from app_model import Application

from varda._actions._file_actions import FILE_ACTIONS
from varda._actions._workspace_actions import WORKSPACE_ACTIONS
from varda._actions._debug_actions import DEBUG_ACTIONS
from varda._actions._menu_ids import MENUBAR as MENUBAR

ALL_ACTIONS = [*FILE_ACTIONS, *WORKSPACE_ACTIONS, *DEBUG_ACTIONS]


def registerAllActions(app: Application) -> None:
    """Register all built-in Varda actions with the application."""
    for action in ALL_ACTIONS:
        app.register_action(action)
