from app_model.types import Action, MenuRule

from varda._actions._context_keys import EXPR_HAS_IMAGES
from varda._actions._menu_ids import MenuId, MenuGroup
from varda.common.observable_list import ImageList
from varda.maingui import MainGUI
from varda.workspaces.dual_image_workspace import NewDualImageWorkspaceDialog
from varda.workspaces.general_image_analysis import (
    NewGeneralImageAnalysisWorkspaceDialog,
)


def newDualImageWorkspace(images: ImageList, mainGui: MainGUI) -> None:
    NewDualImageWorkspaceDialog(images).connectOnAccept(
        lambda workspace: mainGui.addTab(workspace, "Dual Image Workspace")
    ).open()


def newGeneralAnalysisWorkspace(images: ImageList, mainGui: MainGUI) -> None:
    NewGeneralImageAnalysisWorkspaceDialog(images).connectOnAccept(
        lambda workspace: mainGui.addTab(workspace, "General Image Analysis Workspace")
    ).open()


WORKSPACE_ACTIONS: list[Action] = [
    Action(
        id="varda.workspace.new_dual_image",
        title="New Dual Image Workspace",
        callback=newDualImageWorkspace,
        enablement=EXPR_HAS_IMAGES,
        menus=[MenuRule(id=MenuId.WORKSPACE, group=MenuGroup.WORKSPACE_NEW, order=1)],
    ),
    Action(
        id="varda.workspace.new_general_analysis",
        title="New General Image Analysis Workspace",
        callback=newGeneralAnalysisWorkspace,
        enablement=EXPR_HAS_IMAGES,
        menus=[MenuRule(id=MenuId.WORKSPACE, group=MenuGroup.WORKSPACE_NEW, order=2)],
    ),
]
