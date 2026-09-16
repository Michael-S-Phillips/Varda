"""Declarative app_model actions for the image list's right-click menu.

Mirrors ``viewport_actions``: the actions operate on a transient
``ImageListClickContext`` set just before the menu is shown (or a command is
run directly), supplied to callbacks via the app's injection store.
"""

from __future__ import annotations

import attrs
from app_model.types import Action, MenuRule

from varda.common.di_types import ProjectImages
from varda.common.entities import VardaRaster
from varda.maingui import MainGUI
from varda.workspaces.dual_image_workspace import NewDualImageWorkspaceDialog
from varda.workspaces.general_image_analysis import (
    GeneralImageAnalysisConfig,
    GeneralImageAnalysisWorkflow,
)

IMAGE_LIST_CONTEXT_MENU_ID = "varda/image_list/context"
OPEN_GENERAL_ANALYSIS_ID = "varda.image_list.open_general_analysis"
OPEN_DUAL_IMAGE_ID = "varda.image_list.open_dual_image"


@attrs.define
class ImageListClickContext:
    """Transient state for the current interaction with the image list.

    ``images`` holds the clicked image first, followed by any other selected images.
    """

    images: list[VardaRaster]


_current: ImageListClickContext | None = None


def setCurrentClickContext(ctx: ImageListClickContext | None) -> None:
    global _current
    _current = ctx


def getCurrentClickContext() -> ImageListClickContext | None:
    return _current


def _openInGeneralAnalysis(
    ctx: ImageListClickContext, images: ProjectImages, mainGui: MainGUI
) -> None:
    # The workflow reads its image once at construction, so a snapshot suffices.
    config = GeneralImageAnalysisConfig(list(images))
    config.image.set(ctx.images[0])
    mainGui.addTab(
        GeneralImageAnalysisWorkflow(config), "General Image Analysis Workspace"
    )


def _openInDualImage(
    ctx: ImageListClickContext, images: ProjectImages, mainGui: MainGUI
) -> None:
    # With exactly two images selected, fill both slots; otherwise the user picks
    # the secondary image in the dialog.
    secondary = ctx.images[1] if len(ctx.images) == 2 else None
    NewDualImageWorkspaceDialog(
        images, primary=ctx.images[0], secondary=secondary
    ).connectOnAccept(
        lambda workspace: mainGui.addTab(workspace, "Dual Image Workspace")
    ).open()


IMAGE_LIST_ACTIONS: list[Action] = [
    Action(
        id=OPEN_GENERAL_ANALYSIS_ID,
        title="Open in New General Analysis Workspace",
        callback=_openInGeneralAnalysis,
        menus=[MenuRule(id=IMAGE_LIST_CONTEXT_MENU_ID, order=1)],
    ),
    Action(
        id=OPEN_DUAL_IMAGE_ID,
        title="Open in New Dual Image Workspace…",
        callback=_openInDualImage,
        menus=[MenuRule(id=IMAGE_LIST_CONTEXT_MENU_ID, order=2)],
    ),
]
