from app_model.types import Action, MenuRule, StandardKeyBinding

from varda._actions._menu_ids import MenuGroup, MenuId
from varda.context_keys import EXPR_HAS_IMAGES, EXPR_HAS_WORKSPACE
from varda.common.di_types import ProjectImages
from varda.maingui import MainGUI
from varda.workspaces.dual_image_workspace import NewDualImageWorkspaceDialog
from varda.workspaces.general_image_analysis import (
    NewGeneralImageAnalysisWorkspaceDialog,
)


def newDualImageWorkspace(images: ProjectImages, mainGui: MainGUI) -> None:
    NewDualImageWorkspaceDialog(images).connectOnAccept(mainGui.addTab).open()


def newGeneralAnalysisWorkspace(images: ProjectImages, mainGui: MainGUI) -> None:
    NewGeneralImageAnalysisWorkspaceDialog(images).connectOnAccept(
        mainGui.addTab
    ).open()


def closeCurrentWorkspace(mainGui: MainGUI) -> None:
    mainGui.closeWorkspace(mainGui.currentWorkspace())


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
    Action(
        id="varda.workspace.close",
        title="Close Workspace",
        callback=closeCurrentWorkspace,
        enablement=EXPR_HAS_WORKSPACE,
        menus=[
            MenuRule(id=MenuId.WORKSPACE, group=MenuGroup.WORKSPACE_MANAGE, order=1)
        ],
        keybindings=[StandardKeyBinding.Close.to_keybinding_rule()],
    ),
]
