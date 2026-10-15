"""Puts plugins' contributions into the running app: analyses as Processing
menu items (with a submenu for any new category), listed in the Plugins menu
too, and file formats in the data source registry. Everything added can be taken away again, so plugins
can be disabled, reloaded or removed while Varda runs."""

from __future__ import annotations

from collections.abc import Callable

from app_model import Application
from app_model.types import MenuRule

from varda.catalogs.registry import catalogRegistry
from varda._actions._menu_ids import MenuGroup, MenuId
from varda._actions._processing_actions import (
    _menuCallback,
    _slug,
    processingActions,
    submenuItem,
)
from varda.analysis.analysis import categoryLevels
from varda.analysis.registry import ANALYSES
from varda.image_loading.data_sources.registry import (
    RegisteredDataSource,
    datasource_registry,
)
from varda.plugins.plugin_manager import Contributions

PLUGIN_CATEGORY_ORDER = 100  # plugins' own submenus come after Varda's


class AppContributionSink:
    def __init__(self, app: Application) -> None:
        self._app = app
        # every menu level Varda's own analyses use ("Filtering", "Filtering/Spatial")
        self._builtinLevels = {
            level
            for analysis in ANALYSES
            for level in categoryLevels(analysis.category)
        }
        # a plugin's new menu level -> (plugins using it, how to remove its submenu)
        self._submenus: dict[str, tuple[int, Callable[[], None]]] = {}

    def add(self, plugin: str, contributions: Contributions) -> Callable[[], None]:
        removers: list[Callable[[], None]] = []
        analyses = contributions.analyses
        if analyses:
            levels = dict.fromkeys(
                level for a in analyses for level in categoryLevels(a.category)
            )
            for level in levels:
                if level not in self._builtinLevels:
                    removers.append(self._useLevel(level))
            actions = processingActions(
                MenuId.PROCESSING,
                f"varda.plugin.{_slug(plugin)}",
                analyses,
                _menuCallback,
            )
            # Also under Plugins, where people look for what a plugin added
            inPlugins = MenuRule(id=MenuId.PLUGINS, group=MenuGroup.PLUGINS_FEATURES)
            actions = [
                a.model_copy(update={"menus": [*(a.menus or []), inPlugins]})
                for a in actions
            ]
            removers.append(self._app.register_actions(actions))
        for formatName, extensions, cls in contributions.dataSources:
            entry = RegisteredDataSource(formatName, extensions, cls)
            datasource_registry.append(entry)
            removers.append(lambda entry=entry: datasource_registry.remove(entry))
        for catalog in contributions.catalogs:
            catalogRegistry.append(catalog)
            removers.append(lambda catalog=catalog: catalogRegistry.remove(catalog))

        def remove() -> None:
            for remover in reversed(removers):
                remover()

        return remove

    def _useLevel(self, level: str) -> Callable[[], None]:
        """A Processing submenu for a plugin's own category (or a level of
        its path), shared by every plugin using it and removed with the last."""
        users, removeSubmenu = self._submenus.get(level, (0, None))
        if removeSubmenu is None:
            removeSubmenu = self._app.menus.append_menu_items(
                [
                    submenuItem(
                        MenuId.PROCESSING,
                        level,
                        PLUGIN_CATEGORY_ORDER + len(self._submenus),
                    )
                ]
            )
        self._submenus[level] = (users + 1, removeSubmenu)

        def release() -> None:
            count, remover = self._submenus[level]
            if count == 1:
                remover()
                del self._submenus[level]
            else:
                self._submenus[level] = (count - 1, remover)

        return release
