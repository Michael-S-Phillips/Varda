from src import varda


@varda.api.hookimpl
def onLoad():
    """Hook called on plugin load."""
    print("Plugin loaded: print_on_startup :O")