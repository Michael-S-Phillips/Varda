"""Where a kindled feature goes: the Processing menu's categories (Varda's own
and installed plugins'), and whether a new category merely duplicates one of
them ("Filters" beside "Filtering"), which the checks reject."""

from __future__ import annotations

import os
import re
from collections.abc import Iterable
from difflib import SequenceMatcher

from varda.analysis.analysis import SUBMENU, categoryLevels
from varda.analysis.registry import ANALYSES
from varda.plugins.plugin_manager import VardaPluginManager

SHARED_PREFIX = 0.7  # of the shorter name: "Filters" is "Filtering" with another ending
MIN_PREFIX = 5
SIMILAR = 0.85  # SequenceMatcher ratio for typos ("Filtring")


def menuCategories(manager: VardaPluginManager | None = None) -> list[str]:
    """Processing submenus in menu order: Varda's, then installed plugins'."""
    categories = [a.category for a in ANALYSES]
    if manager is not None:
        for record in manager.records:
            categories += [a.category for a in record.contributions.analyses]
    return list(dict.fromkeys(categories))


def _letters(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _same(a: str, b: str) -> bool:
    a, b = _letters(a), _letters(b)
    prefix = len(os.path.commonprefix([a, b]))
    if prefix >= MIN_PREFIX and prefix >= SHARED_PREFIX * min(len(a), len(b)):
        return True
    return SequenceMatcher(None, a, b).ratio() >= SIMILAR


def duplicateOf(category: str, existing: Iterable[str]) -> str:
    """The existing category ``category`` duplicates, or "" if it's either
    one of them exactly or genuinely new."""
    existing = list(existing)
    if category in existing:
        return ""
    return next((name for name in existing if _same(name, category)), "")


def submenusOf(level: str, categories: Iterable[str]) -> list[str]:
    """The categories inside menu ``level`` ("Filtering" holds
    "Filtering/Spatial" and "Filtering/Spectral")."""
    return [c for c in categories if c.startswith(level + SUBMENU)]


def placementProblem(name: str, category: str, categories: Iterable[str]) -> str:
    """Why ``category`` is a poor place for analysis ``name`` among the
    menu's ``categories`` (paths), or "" if it's fine."""
    categories = list(categories)
    levels = list(
        dict.fromkeys(level for c in categories for level in categoryLevels(c))
    )
    duplicate = category if category in levels else duplicateOf(category, levels)
    if not duplicate:
        return ""
    inside = submenusOf(duplicate, categories)
    if inside:
        choices = ", ".join(repr(c) for c in inside)
        return (
            f"{name}'s category {category!r} is the {duplicate!r} menu, which has "
            f"submenus: set category to one of {choices}."
        )
    if duplicate == category:
        return ""
    return (
        f"{name}'s category {category!r} duplicates the existing {duplicate!r} "
        f"menu: set category = {duplicate!r}."
    )
