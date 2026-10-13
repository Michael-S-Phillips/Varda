"""
Plugin manager for the Varda application.
"""

import importlib.util
import logging
import sys
from pathlib import Path
from types import ModuleType

from pluggy import PluginManager

import varda

logger = logging.getLogger(__name__)

SKIPPED_FOLDER = "examples"  # sample plugins, documentation only


def _importFromPath(moduleName: str, source: Path) -> ModuleType:
    """Import a plugin file or package ``__init__.py`` under ``moduleName``."""
    spec = importlib.util.spec_from_file_location(
        moduleName,
        source,
        submodule_search_locations=[str(source.parent)]
        if source.name == "__init__.py"
        else None,
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot import {source}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[moduleName] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        del sys.modules[moduleName]
        raise
    return module


class VardaPluginManager:
    """
    PluginManager for Varda that automatically discovers and loads plugins.
    """

    def __init__(self):
        self.pm = PluginManager("varda")
        self.pm.add_hookspecs(varda.plugins._hooks)
        self.pm.register(varda.plugins._hooks)
        # load plugins from entrypoints
        self.pm.load_setuptools_entrypoints("varda.plugins")

        # load plugins from local "user_plugins" package
        # plugins can either be standalone .py files, or an installed package
        currPath = Path(varda.__file__).resolve().parent
        pluginFolder = currPath / "plugins" / "user_plugins"
        self._registerPluginsInFolder(pluginFolder)

    def _registerPluginsInFolder(self, pluginFolder: Path) -> None:
        """Register each plugin in ``pluginFolder``: a ``.py`` file or a package.

        Skipped: the packaged app (its folder isn't user-editable), the
        ``examples`` folder, and names starting with ``_``. A plugin that fails
        to import is logged and skipped so it can't stop Varda starting.
        """
        if getattr(sys, "frozen", False):
            logger.info("Packaged app: not loading plugins from %s", pluginFolder)
            return
        for path in sorted(Path(pluginFolder).iterdir()):
            name = path.name
            if name.startswith("_") or name == SKIPPED_FOLDER:
                continue
            if path.suffix == ".py":
                moduleName, source = path.stem, path
            elif path.is_dir() and (path / "__init__.py").is_file():
                moduleName, source = name, path / "__init__.py"
            else:
                continue
            try:
                module = _importFromPath(f"varda_user_plugin_{moduleName}", source)
            except Exception:  # a broken plugin must not stop Varda starting
                logger.exception("Could not load plugin %s", path)
                continue
            self.pm.register(module, name=moduleName)

    @property
    def hook(self):
        """
        Access the hook interface of the plugin manager.
        """
        return self.pm.hook
