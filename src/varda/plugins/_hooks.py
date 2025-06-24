import pluggy

hookspec = pluggy.HookspecMarker("varda")
hookimpl = pluggy.HookimplMarker("varda")

@hookspec
def onLoad():
    """Hook called on plugin load."""

@hookspec
def onUnload():
    """Hook called on plugin unload."""