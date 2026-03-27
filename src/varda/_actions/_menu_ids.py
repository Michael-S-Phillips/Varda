class MenuId:
    FILE = "varda/file"
    WORKSPACE = "varda/workspace"
    DEBUG = "varda/debug"


class MenuGroup:
    FILE_IO = "1_io"
    FILE_EXIT = "9_exit"
    WORKSPACE_NEW = "1_new"
    DEBUG_TESTING = "1_testing"


MENUBAR: list[tuple[str, str]] = [
    (MenuId.FILE, "File"),
    (MenuId.WORKSPACE, "Workspace"),
    (MenuId.DEBUG, "Debug"),
]
