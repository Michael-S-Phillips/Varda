"""The View menu: which panels of the main window are showing."""

from __future__ import annotations

from app_model.types import Action, MenuRule, ToggleRule

from varda._actions._menu_ids import MenuId
from varda.context_keys import EXPR_IMAGE_LIST_VISIBLE
from varda.maingui import MainGUI


def toggleImageList(mainGui: MainGUI) -> None:
    mainGui.toggleImageList()


VIEW_ACTIONS: list[Action] = [
    Action(
        id="varda.view.image_list",
        title="Image List",
        tooltip="Show or hide the list of open images",
        callback=toggleImageList,
        toggled=ToggleRule(condition=EXPR_IMAGE_LIST_VISIBLE),
        menus=[MenuRule(id=MenuId.VIEW, order=1)],
    ),
]
