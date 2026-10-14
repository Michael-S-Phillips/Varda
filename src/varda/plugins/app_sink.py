"""Puts plugins' contributions into the running app: analyses as Processing
menu items (with a submenu for any new category) and file formats in the
data source registry. Everything added can be taken away again, so plugins
can be disabled, reloaded or removed while Varda runs."""

from __future__ import annotations

from collections.abc import Callable

from app_model import Application
from app_model.types import SubmenuItem

from varda._actions._menu_ids import MenuId
from varda._actions._processing_actions import (
    _menuCallback,
    _slug,
    categoryMenuId,
    processingActions,
)
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
        self._builtinCategories = {analysis.category for analysis in ANALYSES}
        # new category -> (plugins using it, how to remove its submenu)
        self._submenus: dict[str, tuple[int, Callable[[], None]]] = {}

    def add(self, plugin: str, contributions: Contributions) -> Callable[[], None]:
        removers: list[Callable[[], None]] = []
        analyses = contributions.analyses
        if analyses:
            for category in dict.fromkeys(a.category for a in analyses):
                if category not in self._builtinCategories:
                    removers.append(self._useCategory(category))
            actions = processingActions(
                MenuId.PROCESSING,
                f"varda.plugin.{_slug(plugin)}",
                analyses,
                _menuCallback,
            )
            removers.append(self._app.register_actions(actions))
        for formatName, extensions, cls in contributions.dataSources:
            entry = RegisteredDataSource(formatName, extensions, cls)
            datasource_registry.append(entry)
            removers.append(lambda entry=entry: datasource_registry.remove(entry))

        def remove() -> None:
            for remover in reversed(removers):
                remover()

        return remove

    def _useCategory(self, category: str) -> Callable[[], None]:
        """A Processing submenu for a plugin's own category, shared by every
        plugin using it and removed with the last one."""
        users, removeSubmenu = self._submenus.get(category, (0, None))
        if removeSubmenu is None:
            item = SubmenuItem(
                submenu=categoryMenuId(MenuId.PROCESSING, category),
                title=category,
                order=PLUGIN_CATEGORY_ORDER + len(self._submenus),
            )
            removeSubmenu = self._app.menus.append_menu_items(
                [(MenuId.PROCESSING, item)]
            )
        self._submenus[category] = (users + 1, removeSubmenu)

        def release() -> None:
            count, remover = self._submenus[category]
            if count == 1:
                remover()
                del self._submenus[category]
            else:
                self._submenus[category] = (count - 1, remover)

        return release
