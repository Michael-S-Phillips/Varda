"""The Plugins menu: manage installed plugins and install new ones."""

from __future__ import annotations

from app_model.types import Action, MenuRule

from varda._actions._menu_ids import MenuGroup, MenuId
from varda.common.ui import openOwnedDialog
from varda.maingui import MainGUI
from varda.plugins.plugin_manager import VardaPluginManager
from varda.plugins.plugins_dialog import (
    ManagePluginsDialog,
    chooseFolder,
    chooseZip,
    installPlugin,
)


def managePlugins(manager: VardaPluginManager, mainGui: MainGUI) -> None:
    openOwnedDialog(ManagePluginsDialog(manager, parent=mainGui))


def installFromFolder(manager: VardaPluginManager, mainGui: MainGUI) -> None:
    folder = chooseFolder(mainGui)
    if folder is not None:
        installPlugin(manager, folder, mainGui)


def installFromZip(manager: VardaPluginManager, mainGui: MainGUI) -> None:
    archive = chooseZip(mainGui)
    if archive is not None:
        installPlugin(manager, archive, mainGui)


PLUGIN_ACTIONS: list[Action] = [
    Action(
        id="varda.plugins.manage",
        title="Manage Plugins…",
        tooltip="See installed plugins and what they add; enable, disable, reload or remove them",
        callback=managePlugins,
        menus=[MenuRule(id=MenuId.PLUGINS, group=MenuGroup.PLUGINS_MANAGE, order=1)],
    ),
    Action(
        id="varda.plugins.install_folder",
        title="Install from Folder…",
        tooltip="Install a plugin from a folder containing plugin.toml",
        callback=installFromFolder,
        menus=[MenuRule(id=MenuId.PLUGINS, group=MenuGroup.PLUGINS_INSTALL, order=1)],
    ),
    Action(
        id="varda.plugins.install_zip",
        title="Install from Zip…",
        tooltip="Install a plugin from a .zip of its folder",
        callback=installFromZip,
        menus=[MenuRule(id=MenuId.PLUGINS, group=MenuGroup.PLUGINS_INSTALL, order=2)],
    ),
]
