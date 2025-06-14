import pluggy

hookspec = pluggy.HookspecMarker("varda")

@hookspec
def onLoad():
    """Hook called on plugin load."""
