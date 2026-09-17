from varda._actions._analysis_actions import ANALYSIS_ACTIONS
from varda._actions._debug_actions import DEBUG_ACTIONS
from varda._actions._file_actions import FILE_ACTIONS
from varda._actions._menu_ids import MENUBAR as MENUBAR
from varda._actions._workspace_actions import WORKSPACE_ACTIONS

ALL_ACTIONS = [*FILE_ACTIONS, *WORKSPACE_ACTIONS, *ANALYSIS_ACTIONS, *DEBUG_ACTIONS]
