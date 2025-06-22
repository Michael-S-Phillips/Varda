import importlib
from pathlib import Path

from pluggy import PluginManager

import varda


class VardaPluginManager:
    """
    PluginManager for Varda that automatically discovers and loads plugins.
    """

    def __init__(self):
        self.pm = PluginManager("varda")
        self.pm.add_hookspecs(varda.plugins._hookspecs)
        # load plugins from entrypoints
        self.pm.load_setuptools_entrypoints("varda.plugins")

        # load plugins from local "user_plugins" package
        # plugins can either be standalone .py files, or an installed package
        currPath = Path(__file__).resolve().parent
        pluginFolder = currPath / "plugins/user_plugins"
        self._registerPluginsInFolder(pluginFolder)

    def _registerPluginsInFolder(self, pluginFolder):
        for name in pluginFolder.iterdir():
            name = name.name
            path = pluginFolder.joinpath(name)
            if name.endswith(".py"):
                # plugin is a standalone file
                moduleName = name[:-3]
            elif path.is_dir() and path.joinpath("__init__.py").is_file():
                # plugin is a package
                moduleName = name
            else:
                continue
            mod = importlib.import_module(f"varda.plugins.user_plugins.{moduleName}")
            self.pm.register(mod)
