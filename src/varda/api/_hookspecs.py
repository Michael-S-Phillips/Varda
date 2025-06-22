import pluggy

hookspec = pluggy.HookspecMarker("varda")


@hookspec
def onLoad():
    """Hook called on plugin load."""


@hookspec
def onUnload():
    """Hook called on plugin unload."""
