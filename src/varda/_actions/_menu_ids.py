from enum import StrEnum


class MenuId(StrEnum):
    FILE = "varda/file"
    WORKSPACE = "varda/workspace"
    PROCESSING = "varda/processing"
    DEBUG = "varda/debug"
    HELP = "varda/help"


class MenuGroup(StrEnum):
    FILE_IO = "1_io"
    FILE_SESSION = "2_session"
    FILE_EXIT = "9_exit"
    WORKSPACE_NEW = "1_new"
    WORKSPACE_MANAGE = "2_manage"
    DEBUG_TESTING = "1_testing"
    HELP_LINKS = "1_links"
    HELP_INFO = "2_info"
    HELP_ABOUT = "9_about"


MENUBAR: list[tuple[str, str]] = [
    (MenuId.FILE, "File"),
    (MenuId.WORKSPACE, "Workspace"),
    (MenuId.PROCESSING, "Processing"),
    (MenuId.DEBUG, "Debug"),
    (MenuId.HELP, "Help"),
]
