"""Declarative app_model actions for the raster viewport's right-click menu.

Co-located with the viewport (not in the global ``_actions/`` package): each
subsystem owns its actions. The actions operate on a transient
``ViewportClickContext`` set just before the menu is shown, supplied to callbacks
via the app's injection store (app_model resolves callback args by type).
"""

from __future__ import annotations

from collections.abc import Callable

import attrs
from app_model.types import Action, MenuRule

VIEWPORT_CONTEXT_MENU_ID = "varda/viewport/context"


@attrs.define
class ViewportClickContext:
    """Transient state for the current right-click on a viewport."""

    placeTemplate: Callable[[], None]


_current: ViewportClickContext | None = None


def setCurrentClickContext(ctx: ViewportClickContext | None) -> None:
    global _current
    _current = ctx


def getCurrentClickContext() -> ViewportClickContext | None:
    return _current


def _placeTemplateHere(ctx: ViewportClickContext) -> None:
    ctx.placeTemplate()


VIEWPORT_ACTIONS: list[Action] = [
    Action(
        id="varda.viewport.place_template",
        title="Place template here",
        callback=_placeTemplateHere,
        menus=[MenuRule(id=VIEWPORT_CONTEXT_MENU_ID)],
    ),
]
