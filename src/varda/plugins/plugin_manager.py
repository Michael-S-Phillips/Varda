import importlib
from pathlib import Path

from pluggy import PluginManager

import varda

def initPluginManager():
    """
    Initialize the plugin manager and load plugins.

    Plugins installed with pip/conda will be automatically detected.
    Plugins can also be placed inside the user_plugins folder,
    this is easier for quick testing or writing plugins you don't intend to publish.
    """
    pm = PluginManager("varda")
    pm.add_hookspecs(varda.api._hookspecs)
    # load plugins from entrypoints
    pm.load_setuptools_entrypoints("varda.plugins")

    # load plugins from local "user_plugins" package
    # plugins can either be standalone py files, or a package
    currPath = Path(__file__).resolve().parent
    pluginFolder = currPath / "user_plugins"
    registerPluginsInFolder(pm, pluginFolder)
    return pm

def registerPluginsInFolder(pm, pluginFolder):
    for name in pluginFolder.iterdir():
        name = name.name
        path = pluginFolder.joinpath(name)
        if name.endswith('.py'):
            # plugin is a standalone file
            moduleName = name[:-3]
        elif path.is_dir() and path.joinpath('__init__.py').is_file():
            # plugin is a package
            moduleName = name
        else:
            continue
        mod = importlib.import_module(f"varda.plugins.user_plugins.{moduleName}")
        pm.register(mod)